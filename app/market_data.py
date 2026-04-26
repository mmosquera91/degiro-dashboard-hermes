"""yfinance enrichment — current prices, 52w range, RSI, performance, sector, FX rates."""

import json
import logging
import math
import os
import pathlib
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
_SYMBOL_CACHE_PATH = "/data/snapshots/symbol_cache.json"

# ISIN → Yahoo ticker overrides (user-maintained, loaded from disk)
SYMBOL_OVERRIDES_PATH = pathlib.Path(
    os.environ.get("SYMBOL_OVERRIDES_PATH", "/data/symbol_overrides.json")
)
_symbol_overrides: dict[str, str] = {}
_symbol_overrides_lock = threading.Lock()

def _load_symbol_overrides() -> None:
    """Load ISIN → Yahoo symbol overrides from disk.

    File format (ISIN as key, Yahoo ticker as value):
    {
        "IE00BMCX4Z88": "SXRU.AS",
        "IE00BYX5NX33": "6RV.DE",
        "LU1681043910": "O9T.DE"
    }
    """
    global _symbol_overrides
    if not SYMBOL_OVERRIDES_PATH.exists():
        return
    try:
        with open(SYMBOL_OVERRIDES_PATH, "r") as f:
            data = json.load(f)
        with _symbol_overrides_lock:
            _symbol_overrides = {k.strip().upper(): v.strip() for k, v in data.items() if k and v}
        logger.info("Loaded %d symbol overrides from %s",
                    len(_symbol_overrides), SYMBOL_OVERRIDES_PATH)
    except Exception as e:
        logger.warning("Failed to load symbol overrides: %s", e)

# DeGiro exchangeId → Yahoo Finance suffix.
# Source: DeGiro product API exchangeId values observed in practice.
_DEGIRO_EXCHANGE_TO_YF_SUFFIX: dict[str, str] = {
    # Euronext
    "200": ".AS",   # Euronext Amsterdam
    "394": ".PA",   # Euronext Paris
    "490": ".BR",   # Euronext Brussels
    "314": ".LS",   # Euronext Lisbon
    # Germany
    "645": ".DE",   # Xetra (Deutsche Börse)
    "72":  ".F",    # Frankfurt (secondary)
    # UK
    "663": ".L",    # London Stock Exchange
    # Nordic
    "109": ".HE",   # Helsinki (Nasdaq Nordic)
    "194": ".ST",   # Stockholm
    "518": ".OL",   # Oslo
    "735": ".CO",   # Copenhagen
    # Southern Europe
    "296": ".MI",   # Borsa Italiana (Milan)
    "750": ".MC",   # Bolsa de Madrid
    # Switzerland
    "455": ".SW",   # SIX Swiss Exchange
    # US — bare ticker (no suffix)
    "676": "",      # NASDAQ
    "663": "",      # NYSE (shares exchangeId with LSE — see note below)
    "13":  "",      # NYSE (alternate)
    "14":  "",      # NASDAQ (alternate)
    "75":  "",      # NASDAQ (alternate)
    "71":  "",      # NYSE MKT (AMEX)
    # Canada
    "130": ".TO",   # Toronto Stock Exchange
    "490": ".V",    # TSX Venture
    # Asia-Pacific
    "737": ".SI",   # Singapore Exchange
    "225": ".T",    # Tokyo Stock Exchange
    "240": ".HK",   # Hong Kong
}

# NOTE: DeGiro uses exchangeId=663 for both LSE and NYSE in some DeGiro responses.
# When this ambiguity is hit, fall through to the ISIN-prefix heuristic or suffix
# scan as tiebreaker.


def _suffix_from_exchange_id(exchange_id: str, isin: str = "") -> Optional[str]:
    """Derive Yahoo Finance suffix from DeGiro exchangeId.

    Handles the LSE/NYSE ambiguity (both use 663 in some DeGiro responses)
    by using the ISIN country prefix as a tiebreaker.
    """
    if not exchange_id:
        return None  # None means "unknown" — fall through to scan
    suffix = _DEGIRO_EXCHANGE_TO_YF_SUFFIX.get(str(exchange_id))
    if suffix is None:
        return None

    # Tiebreak 663: GB ISIN → .L (LSE), US ISIN → "" (NYSE)
    if exchange_id == "663" and isin:
        prefix = isin[:2].upper()
        if prefix == "US":
            return ""
        if prefix == "GB":
            return ".L"

    return suffix


# Rate limiting: min seconds between yfinance requests
_YF_DELAY = 0.2
_last_yf_request = 0.0

# Global rate-limit flag: once 429 is hit, skip all suffix scanning for 60 seconds
_yf_rate_limited: bool = False
_yf_rate_limited_until: float = 0.0
_yf_rate_limited_lock = threading.RLock()

def _load_symbol_cache() -> None:
    """Load persisted symbol cache from disk into _symbol_cache."""
    global _symbol_cache
    _load_symbol_overrides()
    try:
        if os.path.exists(_SYMBOL_CACHE_PATH):
            with open(_SYMBOL_CACHE_PATH, "r") as f:
                data = json.load(f)
            with _symbol_cache_lock:
                _symbol_cache.update(data)
            logger.info("Loaded %d symbol cache entries from disk", len(data))
    except Exception as e:
        logger.warning("Could not load symbol cache: %s", e)


def _save_symbol_cache() -> None:
    """Persist current symbol cache to disk."""
    try:
        os.makedirs(os.path.dirname(_SYMBOL_CACHE_PATH), exist_ok=True)
        with _symbol_cache_lock:
            data = dict(_symbol_cache)
        tmp_path = _SYMBOL_CACHE_PATH + ".tmp"
        with open(tmp_path, "w") as f:
            json.dump(data, f)
        os.replace(tmp_path, _SYMBOL_CACHE_PATH)
    except Exception as e:
        logger.warning("Could not save symbol cache: %s", e)


# Load persisted symbol cache from previous runs
_load_symbol_cache()



def _resolve_by_isin(isin: str, position_currency: str = "EUR") -> str:
    """Resolve a Yahoo Finance ticker from ISIN using yf.Search.

    Prefers results on exchanges matching position_currency.
    Returns empty string if nothing is found or on rate limit.
    """
    if not isin:
        return ""

    _EUR_EXCHANGES = {
        "AMS", "EAM",          # Amsterdam
        "PAR", "EPA",          # Paris
        "FRA", "GER", "ETR",   # Frankfurt / Xetra
        "EBS",                 # Zurich (SIX)
        "MIL", "BIT",          # Milan / Borsa Italiana
        "MCE",                 # Madrid
        "HEL",                 # Helsinki
        "OSL",                 # Oslo
        "BRU", "EBR",          # Brussels
        "LIS", "ELI",          # Lisbon
        "VIE",                 # Vienna
    }
    _USD_EXCHANGES = {"NYQ", "NMS", "NGM", "PCX", "ASE", "CBT"}
    _GBP_EXCHANGES = {"LSE", "IOB"}

    currency_map = {
        "EUR": _EUR_EXCHANGES,
        "USD": _USD_EXCHANGES,
        "GBP": _GBP_EXCHANGES,
    }
    preferred_exchanges = currency_map.get(position_currency.upper(), _EUR_EXCHANGES)

    try:
        _yf_throttle()
        results = yf.Search(isin, max_results=10)
        quotes = results.quotes if hasattr(results, "quotes") else []

        if not quotes:
            return ""

        # First pass: prefer currency-matched exchange
        # Stuttgart ("SG", "STU") and Tradegate ("TDG") return the ISIN itself
        # as the symbol — skip them.
        _ISIN_AS_SYMBOL_EXCHANGES = {"SG", "STU", "TDG"}

        for quote in quotes:
            sym = quote.get("symbol", "")
            exch = quote.get("exchange", "")
            if not sym or not exch:
                continue
            if exch in _ISIN_AS_SYMBOL_EXCHANGES:
                continue  # symbol would be the ISIN string, not a ticker
            if len(sym) > 12:
                continue  # ISIN strings are 12 chars — skip anything that long
            if exch in preferred_exchanges:
                logger.debug("ISIN %s resolved to %s via exchange %s", isin, sym, exch)
                return sym

    except Exception as e:
        err_str = str(e)
        if "429" in err_str or "Too Many Requests" in err_str \
                or "Rate limited" in err_str or "YFRateLimitError" in err_str:
            with _yf_rate_limited_lock:
                _yf_rate_limited = True
                _yf_rate_limited_until = time.time() + 60.0
            logger.warning("Rate limit on ISIN search for %s", isin)
        else:
            logger.debug("ISIN search failed for %s: %s", isin, e)

    return ""


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


def _get_suffix_order(isin: str, symbol: str) -> list[str]:
    """Return suffix scan order optimised for the instrument's likely exchange.

    Routing rules based on ISIN country prefix:
      US / CA       → US markets first; European suffixes are a last resort
      IE / LU       → UCITS ETF; Xetra/London are primary listings
      GB            → London first
      FI            → Helsinki first
      CH            → SIX first
      DE / NL / FR  → Local European exchange first
      Default       → European-first order (portfolio is EUR-heavy)
    """
    prefix = (isin[:2].upper() if isin and len(isin) >= 2 else "")

    if prefix in ("US", "CA"):
        return ["", ".TO", ".AS", ".PA", ".DE", ".L", ".MI",
                ".MC", ".HE", ".F", ".SW", ".SI"]

    if prefix in ("IE", "LU"):
        return [".DE", ".F", ".L", ".AS", ".PA", ".MI", ".MC",
                ".HE", ".SW", ".TO", ".SI", ""]

    if prefix == "GB":
        return [".L", ".DE", ".F", ".AS", ".PA", ".MI", ".MC",
                ".HE", ".SW", ".TO", ".SI", ""]

    if prefix == "FI":
        return [".HE", ".DE", ".F", ".AS", ".PA", ".L", ".MI",
                ".MC", ".SW", ".TO", ".SI", ""]

    if prefix == "CH":
        return [".SW", ".DE", ".F", ".AS", ".PA", ".L", ".MI",
                ".MC", ".HE", ".TO", ".SI", ""]

    if prefix in ("DE", "NL", "FR", "IT", "ES", "BE", "PT", "AT", "NO"):
        return [".AS", ".PA", ".DE", ".L", ".MI", ".MC",
                ".HE", ".F", ".SW", ".TO", ".SI", ""]

    return [".AS", ".PA", ".DE", ".L", ".MI", ".MC",
            ".HE", ".F", ".SW", ".TO", ".SI", ""]


def _resolve_yf_symbol(symbol: str, isin: str = "", position_currency: str = "EUR", exchange_id: str = "") -> str:
    """Resolve a DeGiro symbol to a yfinance-compatible ticker.

    DeGiro symbols sometimes lack exchange suffixes. We try common ones.
    Results are cached in memory and persisted to disk.
    """
    global _yf_rate_limited, _yf_rate_limited_until

    if not symbol:
        return ""

    symbol = symbol.strip()

    # Skip numeric symbols (vwdId leaking through) — never a valid Yahoo ticker
    if symbol.isdigit():
        logger.debug("Skipping numeric symbol %s — not a valid Yahoo ticker", symbol)
        return ""

    # Exchange suffixes are 2+ chars after the dot (e.g. .AS, .PA, .HE).
    # Single-char dots are class indicators (e.g. BRK.B = Class B) — do NOT
    # treat as exchange suffix.
    if "." in symbol:
        after_dot = symbol.rsplit(".", 1)[-1]
        if len(after_dot) >= 2:
            return symbol
        # Single-char dot — normalize to Yahoo dash convention (BRK.B → BRK-B)
        symbol = symbol.rsplit(".", 1)[0] + "-" + after_dot

    cache_key = f"{symbol}:{isin}"

    # Step 0: Deterministic resolution from DeGiro exchangeId (best signal)
    if exchange_id:
        suffix = _suffix_from_exchange_id(exchange_id, isin)
        if suffix is not None:
            candidate = symbol + suffix
            try:
                _yf_throttle()
                t = yf.Ticker(candidate)
                hist = t.history(period="5d")
                if not hist.empty:
                    logger.debug(
                        "Resolved %s via exchangeId %s → %s",
                        symbol, exchange_id, candidate,
                    )
                    with _symbol_cache_lock:
                        _symbol_cache[cache_key] = candidate
                    _save_symbol_cache()
                    return candidate
            except Exception as e:
                logger.debug("exchangeId candidate %s failed: %s", candidate, e)
            # If candidate failed, fall through to ISIN search then suffix scan

    # Step -1: Check manual overrides (ISIN-keyed, highest priority)
    if isin:
        with _symbol_overrides_lock:
            override = _symbol_overrides.get(isin.strip().upper(), "")
        if override:
            logger.debug("Symbol override for ISIN %s: %s", isin, override)
            with _symbol_cache_lock:
                _symbol_cache[cache_key] = override
            _save_symbol_cache()
            return override

    # Check symbol resolution cache first
    with _symbol_cache_lock:
        if cache_key in _symbol_cache:
            cached = _symbol_cache.get(cache_key)
            if cached is not None:
                # Check for 24h negative cache sentinel
                if isinstance(cached, str) and cached.startswith("_notfound_"):
                    try:
                        cached_at = int(cached.split("_notfound_")[1])
                        if time.time() - cached_at < 86400:  # 24 hours
                            return ""  # still within TTL — skip resolution
                        else:
                            # Expired — evict and re-resolve
                            with _symbol_cache_lock:
                                del _symbol_cache[cache_key]
                            _save_symbol_cache()
                    except (IndexError, ValueError):
                        return ""  # malformed sentinel — treat as not-found
                elif cached and cached != symbol:
                    try:
                        _yf_throttle()
                        cached_currency = (yf.Ticker(cached).fast_info.currency or "").upper()
                        pos_currency = position_currency.upper() if position_currency else "EUR"
                        if cached_currency and cached_currency != pos_currency:
                            logger.info(
                                "Evicting stale cache entry %s → %s (yfinance=%s, expected=%s)",
                                cache_key, cached, cached_currency, pos_currency,
                            )
                            with _symbol_cache_lock:
                                del _symbol_cache[cache_key]
                            _save_symbol_cache()
                        else:
                            return cached
                    except Exception:
                        return cached
                else:
                    return cached

    # Step 0: ISIN-based resolution (most accurate — resolves ETFs/ETPs whose
    # DeGiro symbol differs from Yahoo ticker, e.g. QDVD → QDVD.L)
    if isin:
        with _yf_rate_limited_lock:
            if _yf_rate_limited and time.time() < _yf_rate_limited_until:
                logger.warning("Rate limited — skipping ISIN search for %s", symbol)
            else:
                isin_result = _resolve_by_isin(isin, position_currency)
                if isin_result:
                    with _symbol_cache_lock:
                        _symbol_cache[cache_key] = isin_result
                    _save_symbol_cache()
                    return isin_result

    # European suffixes tried first so dual-listed stocks (ASML, TDIV) resolve
    # to the EUR-denominated listing before the bare symbol hits NASDAQ.
    # .HE = Helsinki (Nokia), .F = Frankfurt Xetra ETFs (alternative to .DE).
    # "" (bare) is last — only reached for genuine US-only listings.
    suffixes_to_try = _get_suffix_order(isin, symbol)
    for suffix in suffixes_to_try:
        with _yf_rate_limited_lock:
            if _yf_rate_limited and time.time() < _yf_rate_limited_until:
                logger.warning("Rate limited — skipping suffix scan for %s", symbol)
                return symbol
        candidate = symbol + suffix
        try:
            ticker = yf.Ticker(candidate)
            _yf_throttle()
            info = ticker.info or {}
            if info.get("regularMarketPrice"):
                with _symbol_cache_lock:
                    _symbol_cache[cache_key] = candidate
                _save_symbol_cache()
                return candidate
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "Too Many Requests" in err_str \
                    or "Rate limited" in err_str or "YFRateLimitError" in err_str:
                with _yf_rate_limited_lock:
                    _yf_rate_limited = True
                    _yf_rate_limited_until = time.time() + 60.0
                logger.warning(
                    "Rate limit detected resolving %s — aborting suffix scan", symbol
                )
                return symbol
            # 404 or other error — continue to next suffix

    # All suffixes exhausted — cache the negative result for 24h so next run skips scan
    negative_entry = f"_notfound_{int(time.time())}"
    with _symbol_cache_lock:
        _symbol_cache[cache_key] = negative_entry
    _save_symbol_cache()
    logger.debug("Symbol %s exhausted all suffixes — cached negative result for 24h", symbol)
    return ""


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
        # Make timestamp tz-aware if index is tz-aware (yfinance 1.0+)
        ts_year_start = pd.Timestamp(year_start)
        if hist_close.index.tz is not None:
            ts_year_start = ts_year_start.tz_localize(hist_close.index.tz)
        ytd_mask = hist_close.index >= ts_year_start
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

    yf_symbol = _resolve_yf_symbol(
        symbol, isin, position.get("currency", "EUR"), position.get("exchange_id", "")
    )

    try:
        _yf_throttle()
        ticker = yf.Ticker(yf_symbol)

        # Get info dict for fundamental data
        _yf_throttle()
        try:
            info = ticker.info or {}
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "Too Many Requests" in err_str \
                    or "Rate limited" in err_str:
                position["_enrichment_error"] = "rate_limited"
                logger.warning("Rate limited fetching info for %s", symbol)
                return position
            logger.warning("ticker.info failed for %s: %s", symbol, e)
            info = {}

        # Sector — stocks use "sector"/"industry"; ETFs use "category" as proxy
        if position.get("asset_type") == "ETF":
            position["sector"] = (
                info.get("category")
                or info.get("fundFamily")
                or info.get("industry")
                or None
            )
        else:
            position["sector"] = (
                info.get("sector")
                or info.get("industry")
                or None
            )

        # Country
        position["country"] = info.get("country", None)

        # P/E ratio (stocks only)
        if position.get("asset_type") == "STOCK":
            raw_pe = info.get("trailingPE", info.get("forwardPE", None))
            try:
                position["pe_ratio"] = float(raw_pe) if raw_pe is not None else None
            except (ValueError, TypeError):
                position["pe_ratio"] = None

        # 52-week high/low from info
        wk52_high = info.get("fiftyTwoWeekHigh", None)
        wk52_low = info.get("fiftyTwoWeekLow", None)

        # Determine trading currency from the resolved Yahoo ticker's exchange
        # suffix — this is more reliable than fast_info.currency for ETFs, which
        # reports the index denomination (USD for S&P 500 ETFs), not the listing
        # currency (EUR on AMS/GER for UCITS ETFs).
        yf_currency = ""
        _price_currency_safe = True  # default: trust price if we can't determine

        _EUR_EXCHANGE_SUFFIXES = {".AS", ".PA", ".DE", ".F", ".MI", ".MC",
                                   ".HE", ".SW", ".EAM", ".EPA", ".ETR"}
        _GBP_EXCHANGE_SUFFIXES = {".L"}

        # Extract suffix from resolved symbol (e.g. "SXRU.AS" → ".AS", "QUBT" → "")
        if "." in yf_symbol:
            resolved_suffix = "." + yf_symbol.rsplit(".", 1)[-1]
        else:
            resolved_suffix = ""

        if resolved_suffix in _EUR_EXCHANGE_SUFFIXES:
            yf_currency = "EUR"
        elif resolved_suffix in _GBP_EXCHANGE_SUFFIXES:
            yf_currency = "GBP"

        pos_currency = position.get("currency", "EUR").upper().strip()
        if yf_currency:
            _price_currency_safe = (yf_currency == pos_currency)
        # else: yf_currency unknown → keep _price_currency_safe = True (trust price)

        if not _price_currency_safe:
            logger.warning(
                "Currency mismatch for %s: exchange=%s (%s), position=%s"
                " — keeping DeGiro price",
                symbol, resolved_suffix or "bare", yf_currency, pos_currency,
            )

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

            # Update current price from yfinance only when currencies match.
            # If currencies differ (e.g. USD ticker resolved for a EUR position),
            # keep DeGiro's price — it is always in the correct currency.
            if len(close) > 0 and _price_currency_safe:
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

        # 52w high/low and distance — only write when currencies match.
        # If yfinance price is in a different currency than the position, the
        # 52w absolute values are in the wrong unit and distance_from_52w_high_pct
        # would be a meaningless cross-currency ratio.
        if _price_currency_safe:
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

def _sanitize_floats(obj: dict) -> dict:
    """Replace float inf/nan with None so json.dumps() doesn't crash."""
    return {
        k: (None if isinstance(v, float) and not math.isfinite(v) else v)
        for k, v in obj.items()
    }


def clear_symbol_cache() -> int:
    """Clear the symbol resolution cache (both memory and disk).

    Call this after a yfinance upgrade or when all per-stock metrics show None
    due to poisoned cache entries.
    """
    with _symbol_cache_lock:
        count = len(_symbol_cache)
        _symbol_cache.clear()
    try:
        if os.path.exists(_SYMBOL_CACHE_PATH):
            os.remove(_SYMBOL_CACHE_PATH)
    except OSError:
        pass
    return count


def audit_symbol_cache() -> int:
    """Check symbol cache for entries that resolved to bare symbols (no exchange suffix).

    Such entries indicate the suffix scan was aborted by rate limiting before
    finding a valid suffix — they poison the cache across restarts.

    Returns the count of suspicious entries. Logs a WARNING with remediation advice.
    """
    suspicious = 0
    for bare_symbol, resolved in _symbol_cache.items():
        # resolved has no "." suffix means it was cached as the bare symbol
        if "." not in resolved:
            suspicious += 1
    if suspicious:
        logger.warning(
            "%d suspicious symbol cache entries found (resolved == bare symbol, no suffix). "
            "This indicates rate-limiting aborted the suffix scan. "
            "Call DELETE /api/admin/symbol-cache to clear the cache.",
            suspicious,
        )
    return suspicious

def enrich_positions(raw_portfolio: dict) -> list[dict]:
    """Enrich all positions with yfinance market data.

    Converts values to EUR using FX rates.
    Returns list of enriched position dicts.
    """
    global _yf_rate_limited, _yf_rate_limited_until
    with _yf_rate_limited_lock:
        if time.time() >= _yf_rate_limited_until:
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
            enriched.append(_sanitize_floats(enriched_pos))
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

            enriched.append(_sanitize_floats(enriched_pos))

        except Exception as e:
            logger.warning("Failed to enrich position %s: %s", pos.get("name"), str(e))
            pos["current_value_eur"] = pos.get("current_value", 0)
            pos["unrealized_pl_eur"] = pos.get("unrealized_pl", 0)
            pos["fx_rate"] = 1.0
            for field in ["52w_high", "52w_low", "distance_from_52w_high_pct",
                          "rsi", "perf_30d", "perf_90d", "perf_ytd",
                          "pe_ratio", "sector", "country",
                          "value_score", "momentum_score", "buy_priority_score"]:
                pos.setdefault(field, None)
            enriched.append(_sanitize_floats(pos))

    return enriched
