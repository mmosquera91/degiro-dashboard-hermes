"""yfinance enrichment — current prices, 52w range, RSI, performance, sector, FX rates."""

import logging
import threading
import time
from typing import Optional
from datetime import datetime

import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

# Cache for FX rates to avoid repeated lookups
_fx_cache: dict[str, float] = {}
_fx_lock = threading.RLock()

# Cache for resolved yfinance symbols (symbol:isin -> resolved_yf_symbol)
_symbol_cache: dict[str, str] = {}
_symbol_cache_lock = threading.RLock()

# Rate limiting: min seconds between yfinance requests
_YF_DELAY = 1.0
_last_yf_request = 0.0

# Global rate-limit flag: once 429 is hit, skip all suffix scanning for the session
_yf_rate_limited: bool = False
_yf_rate_limited_lock = threading.RLock()


def _yf_throttle():
    """Sleep if needed to respect rate limits between yfinance calls."""
    global _last_yf_request
    with _fx_lock:
        elapsed = time.time() - _last_yf_request
        if elapsed < _YF_DELAY:
            time.sleep(_YF_DELAY - elapsed)
        _last_yf_request = time.time()


def get_fx_rate(from_currency: str, to_currency: str = "EUR") -> float:
    """Get FX rate to convert from_currency to to_currency."""
    if from_currency == to_currency:
        return 1.0

    key = f"{from_currency}{to_currency}"

    # Read from cache under lock
    with _fx_lock:
        if key in _fx_cache:
            return _fx_cache[key]

    # Fetch outside lock (rate limiting happens inside yfinance calls)
    try:
        # Yahoo Finance uses quote currency as base for =X pairs (EUR is base)
        ticker_map = {
            "USDEUR": "EURUSD=X",   # fetch EURUSD, then invert
            "GBPEUR": "EURGBP=X",   # fetch EURGBP, then invert
            "CHFEUR": "EURCHF=X",
            "JPYEUR": "EURJPY=X",
            "SEKEUR": "EURSEK=X",
            "DKKEUR": "EURDKK=X",
            "NOKEUR": "EURNOK=X",
            "HKDEUR": "EURHKD=X",
            "AUDEUR": "EURAUD=X",
            "CADEUR": "EURCAD=X",
        }
        yf_symbol = ticker_map.get(key, f"{key}=X")
        _yf_throttle()
        ticker = yf.Ticker(yf_symbol)
        _yf_throttle()
        try:
            hist = ticker.history(period="1d", timeout=10)
        except (Exception, OSError) as e:
            logger.warning("yfinance history fetch failed for %s: %s", yf_symbol, e)
            hist = None
        if not hist.empty:
            rate_raw = float(hist["Close"].iloc[-1])
            # Keys where EUR is numerator (must invert the fetched rate)
            inverted_pairs = {
                "USDEUR", "GBPEUR", "CHFEUR", "JPYEUR",
                "SEKEUR", "DKKEUR", "NOKEUR", "HKDEUR",
                "AUDEUR", "CADEUR",
            }
            rate = (1.0 / rate_raw) if key in inverted_pairs else rate_raw
            with _fx_lock:
                _fx_cache[key] = rate
            return rate

        # Fallback: try inverse pair
        inverse_key = f"{to_currency}{from_currency}"
        yf_inverse = f"{inverse_key}=X"
        _yf_throttle()
        ticker_inv = yf.Ticker(yf_inverse)
        _yf_throttle()
        try:
            hist_inv = ticker_inv.history(period="1d", timeout=10)
        except (Exception, OSError) as e:
            logger.warning("yfinance inverse history fetch failed for %s: %s", yf_inverse, e)
            hist_inv = None
        if hist_inv is not None and not hist_inv.empty:
            rate = 1.0 / float(hist_inv["Close"].iloc[-1])
            with _fx_lock:
                _fx_cache[key] = rate
            return rate

    except Exception as e:
        logger.warning("FX rate lookup failed for %s->%s: %s", from_currency, to_currency, str(e))

    logger.warning("FX rate lookup failed for %s->%s — using 1.0 fallback",
                   from_currency, to_currency)
    return 1.0


def _resolve_yf_symbol(symbol: str, isin: str = "") -> str:
    """Resolve a DeGiro symbol to a yfinance-compatible ticker.

    DeGiro symbols sometimes lack exchange suffixes. We add common ones.
    """
    global _yf_rate_limited
    if not symbol:
        return ""

    # Already has an exchange suffix
    if "." in symbol:
        return symbol

    # Check symbol resolution cache first
    cache_key = f"{symbol}:{isin}"
    with _symbol_cache_lock:
        if cache_key in _symbol_cache:
            return _symbol_cache[cache_key]

    # Common European exchanges — try suffixes in order
    suffixes_to_try = ["", ".AS", ".PA", ".DE", ".MI", ".MC", ".L", ".SW", ".TO", ".SI"]
    for suffix in suffixes_to_try:
        with _yf_rate_limited_lock:
            if _yf_rate_limited:
                logger.warning(
                    "Rate limited — skipping suffix scan for %s", symbol
                )
                return symbol
        candidate = symbol + suffix
        try:
            ticker = yf.Ticker(candidate)
            _yf_throttle()
            info = ticker.info
            if info and info.get("regularMarketPrice"):
                with _symbol_cache_lock:
                    _symbol_cache[cache_key] = candidate
                return candidate
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "Too Many Requests" in err_str:
                with _yf_rate_limited_lock:
                    _yf_rate_limited = True
                logger.warning(
                    "Rate limit detected resolving %s — aborting all "
                    "further symbol resolution this session", symbol
                )
                return symbol
            # other exceptions: continue to next suffix

    # Return base symbol as last resort; yfinance will try to resolve it
    return symbol


def compute_rsi(hist_close: pd.Series, period: int = 14) -> Optional[float]:
    """Compute RSI from a series of closing prices."""
    try:
        if len(hist_close) < period + 1:
            return None

        delta = hist_close.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = (-delta).where(delta < 0, 0.0)

        avg_gain = gain.rolling(window=period, min_periods=period).mean()
        avg_loss = loss.rolling(window=period, min_periods=period).mean()

        # Use Wilder's smoothing after initial SMA
        for i in range(period, len(gain)):
            if i >= len(avg_gain):
                break
            avg_gain.iloc[i] = (avg_gain.iloc[i - 1] * (period - 1) + gain.iloc[i]) / period
            avg_loss.iloc[i] = (avg_loss.iloc[i - 1] * (period - 1) + loss.iloc[i]) / period

        if avg_loss.iloc[-1] == 0:
            return 100.0  # No losses = RSI 100
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        result = rsi.dropna()
        if len(result) > 0:
            return round(float(result.iloc[-1]), 2)
        return None

    except Exception as e:
        logger.warning("RSI computation failed: %s", str(e))
        return None


def _compute_performance(hist_close: pd.Series) -> dict:
    """Compute 30d, 90d, YTD performance from closing prices."""
    result = {
        "perf_30d": None,
        "perf_90d": None,
        "perf_ytd": None,
    }

    try:
        if len(hist_close) < 2:
            return result

        current = float(hist_close.iloc[-1])

        # 30-day performance
        if len(hist_close) >= 22:  # ~22 trading days in a month
            price_30d = float(hist_close.iloc[-22])
            if price_30d > 0:
                result["perf_30d"] = round(((current - price_30d) / price_30d) * 100, 2)

        # 90-day performance
        if len(hist_close) >= 63:  # ~63 trading days in 3 months
            price_90d = float(hist_close.iloc[-63])
            if price_90d > 0:
                result["perf_90d"] = round(((current - price_90d) / price_90d) * 100, 2)

        # YTD performance
        now = datetime.now()
        year_start = datetime(now.year, 1, 1)
        ytd_mask = hist_close.index >= pd.Timestamp(year_start)
        ytd_data = hist_close[ytd_mask]
        if len(ytd_data) >= 2:
            price_ytd = float(ytd_data.iloc[0])
            if price_ytd > 0:
                result["perf_ytd"] = round(((current - price_ytd) / price_ytd) * 100, 2)

    except Exception as e:
        logger.warning("Performance computation failed: %s", str(e))

    return result


def enrich_position(position: dict) -> dict:
    """Enrich a single position with yfinance data.

    If yfinance fails for a position, affected fields are set to None.
    The position dict is updated in place and returned.
    """
    symbol = position.get("symbol", "")
    isin = position.get("isin", "")

    # Initialize all yfinance-dependent fields as None
    position["52w_high"] = None
    position["52w_low"] = None
    position["distance_from_52w_high_pct"] = None
    position["rsi"] = None
    position["perf_30d"] = None
    position["perf_90d"] = None
    position["perf_ytd"] = None
    position["pe_ratio"] = None
    position["sector"] = None
    position["country"] = None
    position["value_score"] = None
    position["momentum_score"] = None
    position["buy_priority_score"] = None

    if not symbol:
        logger.warning("No symbol for position: %s (ISIN: %s)", position.get("name"), isin)
        return position

    yf_symbol = _resolve_yf_symbol(symbol, isin)

    try:
        _yf_throttle()
        ticker = yf.Ticker(yf_symbol)

        # Get info dict for fundamental data
        _yf_throttle()
        info = ticker.info or {}

        # Sector
        position["sector"] = info.get("sector", info.get("industry", None))

        # Country
        position["country"] = info.get("country", None)

        # P/E ratio (stocks only)
        if position.get("asset_type") == "STOCK":
            position["pe_ratio"] = info.get("trailingPE", info.get("forwardPE", None))

        # 52-week high/low from info
        wk52_high = info.get("fiftyTwoWeekHigh", None)
        wk52_low = info.get("fiftyTwoWeekLow", None)

        # Get historical data for RSI and performance
        _yf_throttle()
        hist = ticker.history(period="1y")
        if hist is not None and not hist.empty:
            close = hist["Close"]

            # Override 52w high/low from historical if available
            if len(close) > 0:
                hist_high = float(close.max())
                hist_low = float(close.min())
                if wk52_high is None:
                    wk52_high = hist_high
                if wk52_low is None:
                    wk52_low = hist_low

            # RSI
            position["rsi"] = compute_rsi(close, period=14)

            # Performance
            perf = _compute_performance(close)
            position["perf_30d"] = perf["perf_30d"]
            position["perf_90d"] = perf["perf_90d"]
            position["perf_ytd"] = perf["perf_ytd"]

            # Update current price from yfinance if available (more real-time)
            if len(close) > 0:
                yf_price = float(close.iloc[-1])
                if yf_price > 0:
                    position["current_price"] = round(yf_price, 4)
                    position["current_value"] = round(yf_price * position["quantity"], 2)
                    if position["avg_buy_price"] > 0:
                        position["unrealized_pl_pct"] = round(
                            ((yf_price - position["avg_buy_price"]) / position["avg_buy_price"]) * 100, 2
                        )
                        position["unrealized_pl"] = round(
                            (yf_price - position["avg_buy_price"]) * position["quantity"], 2
                        )

        # 52w high/low and distance
        if wk52_high is not None:
            position["52w_high"] = round(float(wk52_high), 4)
        if wk52_low is not None:
            position["52w_low"] = round(float(wk52_low), 4)
        if wk52_high is not None and position.get("current_price", 0) > 0:
            position["distance_from_52w_high_pct"] = round(
                ((position["current_price"] - float(wk52_high)) / float(wk52_high)) * 100, 2
            )

    except Exception as e:
        err_str = str(e)
        if "429" in err_str or "Too Many Requests" in err_str or "Expecting value: line 1 column 1" in err_str:
            position["_enrichment_error"] = "rate_limited"
            logger.warning(
                "Rate limited enriching %s — position marked as rate_limited",
                symbol
            )
        else:
            position["_enrichment_error"] = "yfinance_error"
            logger.warning(
                "yfinance enrichment failed for %s (%s): %s",
                symbol, yf_symbol, str(e)
            )
        return position

    return position


def enrich_positions(raw_portfolio: dict) -> list[dict]:
    """Enrich all positions with yfinance market data.

    Converts values to EUR using FX rates.
    Returns list of enriched position dicts.
    """
    global _yf_rate_limited
    with _yf_rate_limited_lock:
        _yf_rate_limited = False

    positions = raw_portfolio.get("positions", [])
    base_currency = raw_portfolio.get("currency", "EUR")

    # Prefetch FX rates for all unique non-base currencies before the loop
    unique_currencies = {
        pos.get("currency", base_currency)
        for pos in positions
        if pos.get("currency", base_currency) != base_currency
    }
    for currency in unique_currencies:
        get_fx_rate(currency, base_currency)

    enriched = []
    _session_rate_limited = False
    for pos in positions:
        if _session_rate_limited:
            enriched_pos = pos.copy()
            enriched_pos["_enrichment_error"] = "rate_limited_session"
            enriched_pos["current_value_eur"] = pos.get("current_value", 0)
            enriched_pos["unrealized_pl_eur"] = pos.get("unrealized_pl", 0)
            enriched_pos["fx_rate"] = 1.0
            enriched.append(enriched_pos)
            continue

        try:
            enriched_pos = enrich_position(pos.copy())
            if enriched_pos.get("_enrichment_error") == "rate_limited":
                _session_rate_limited = True

            # FX conversion to EUR
            pos_currency = enriched_pos.get("currency", "EUR")
            if pos_currency != base_currency:
                fx_rate = get_fx_rate(pos_currency, base_currency)
                if fx_rate is None:
                    logger.warning("fx_rate is None for %s — falling back to 1.0", pos_currency)
                    fx_rate = 1.0
                enriched_pos["fx_rate"] = fx_rate
                enriched_pos["current_value_eur"] = round(enriched_pos["current_value"] * fx_rate, 2)
                enriched_pos["unrealized_pl_eur"] = round(enriched_pos["unrealized_pl"] * fx_rate, 2)
            else:
                enriched_pos["fx_rate"] = 1.0
                enriched_pos["current_value_eur"] = enriched_pos["current_value"]
                enriched_pos["unrealized_pl_eur"] = enriched_pos["unrealized_pl"]

            enriched.append(enriched_pos)

        except Exception as e:
            logger.warning("Failed to enrich position %s: %s", pos.get("name"), str(e))
            pos["current_value_eur"] = pos["current_value"]
            pos["unrealized_pl_eur"] = pos["unrealized_pl"]
            pos["fx_rate"] = 1.0
            enriched.append(pos)

    return enriched
