"""yfinance enrichment — current prices, 52w range, RSI, performance, sector, FX rates."""

import json
import logging
import math
import os
import pathlib
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional
from datetime import datetime

import numpy as np
import pandas as pd
import yfinance as yf
from yfinance.exceptions import YFTickerMissingError, YFRateLimitError

logger = logging.getLogger(__name__)

# Cache for FX rates to avoid repeated lookups
_fx_cache: dict[str, float] = {}
_fx_lock = threading.RLock()

# Cache for resolved yfinance symbols (symbol:isin -> ResolutionEntry)
# Split into two layers:
#   - Resolution cache (persistent, no TTL): yf_symbol, exchange, currency, method
#   - Price cache (in-memory, 15-min TTL): current_price, price_currency, timestamp
_resolution_cache: dict[str, dict] = {}
_resolution_cache_lock = threading.RLock()
_SYMBOL_CACHE_PATH = "/data/snapshots/symbol_cache.json"

# Price cache: keyed by resolved yf_symbol, 15-min TTL
_price_cache: dict[str, dict] = {}
_price_cache_lock = threading.RLock()
_SYMBOL_CACHE_FILE_LOCK = threading.Lock()
_PRICE_CACHE_TTL = 900  # 15 minutes

# Fundamentals cache: stored inside resolution cache entry, 24h TTL
_FUNDAMENTALS_TTL = 86400  # 24 hours

# ISIN → Yahoo ticker overrides (user-maintained, loaded from disk)
SYMBOL_OVERRIDES_PATH = pathlib.Path(
    os.environ.get("SYMBOL_OVERRIDES_PATH", "/data/symbol_overrides.json")
)
BUNDLED_OVERRIDES_PATH = pathlib.Path(__file__).parent / "bundled_overrides.json"
_symbol_overrides: dict[str, str] = {}
_symbol_overrides_lock = threading.Lock()

def _load_symbol_overrides() -> None:
    """Load ISIN → Yahoo symbol overrides from disk.

    Bundled overrides (ship with the repo) are merged with user overrides
    (from SYMBOL_OVERRIDES_PATH). User overrides take precedence on key conflict.

    File format (ISIN as key, Yahoo ticker as value):
    {
        "IE00BMCX4Z88": "SXRU.AS",
        "IE00BYX5NX33": "6RV.DE",
        "LU1681043910": "O9T.DE"
    }
    """
    global _symbol_overrides

    # 1. Load bundled overrides (empty dict if file missing or invalid)
    bundled_data: dict[str, str] = {}
    try:
        if BUNDLED_OVERRIDES_PATH.exists():
            with open(BUNDLED_OVERRIDES_PATH, "r") as f:
                bundled_data = json.load(f)
    except Exception as e:
        logger.warning("Failed to load bundled overrides: %s", e)

    # 2. Load user overrides (keep existing logic)
    user_data: dict[str, str] = {}
    if SYMBOL_OVERRIDES_PATH.exists():
        try:
            with open(SYMBOL_OVERRIDES_PATH, "r") as f:
                content = f.read().strip()
                if content:
                    user_data = json.loads(content)
        except Exception as e:
            logger.warning("Failed to load symbol overrides: %s", e)

    # 3. Merge — user data wins on key conflict
    merged = {**bundled_data, **user_data}

    # 4. Normalize and store
    with _symbol_overrides_lock:
        _symbol_overrides = {k.strip().upper(): v.strip() for k, v in merged.items() if k and v}

    logger.info("Loaded %d bundled + %d user symbol overrides",
                len(bundled_data), len(user_data))

_DEGIRO_EXCHANGE_TO_YF_SUFFIX: dict[str, str] = {
    # Euronext
    "200": ".AS",   # Euronext Amsterdam
    "394": ".PA",   # Euronext Paris
    "490": ".BR",   # Euronext Brussels
    "314": ".LS",   # Euronext Lisbon

    # Germany — Xetra + all regional exchanges
    "645": ".DE",   # Xetra (Deutsche Börse) — primary German exchange
    "72":  ".F",    # Frankfurt
    "2":   ".HM",   # Hamburg
    "3":   ".BE",   # Berlin
    "4":   ".DU",   # Düsseldorf
    "5":   ".MU",   # Munich
    "6":   ".SG",   # Stuttgart (note: Yahoo .SG = Stuttgart, NOT Singapore)
    "62":  ".F",    # Frankfurt alternate

    # UK
    "663": ".L",    # London Stock Exchange
    "1":   ".L",    # LSE alternate

    # Nordic
    "109": ".HE",   # Helsinki (Nasdaq Nordic)
    "194": ".ST",   # Stockholm (Nasdaq Nordic)
    "518": ".OL",   # Oslo (Oslo Børs)
    "735": ".CO",   # Copenhagen (Nasdaq Nordic)

    # Southern Europe
    "296": ".MI",   # Borsa Italiana (Milan)
    "750": ".MC",   # Bolsa de Madrid

    # Switzerland
    "455": ".SW",   # SIX Swiss Exchange

    # Euronext Fund Services (DeGiro internal — Amundi LU, HSBC IE ETFs)
    "710": ".PA",   # Euronext Paris (primary listing for these funds)

    # US — no suffix (bare ticker)
    "676": "",      # NASDAQ
    "13":  "",      # NYSE
    "14":  "",      # NASDAQ alternate
    "75":  "",      # NASDAQ alternate
    "71":  "",      # NYSE MKT (AMEX)
    "25":  "",      # NYSE alternate

    # Canada
    "130": ".TO",   # Toronto Stock Exchange
    "138": ".V",    # TSX Venture Exchange

    # Asia-Pacific
    "737": ".SI",   # Singapore Exchange (SGX)
    "225": ".T",    # Tokyo Stock Exchange
    "240": ".HK",   # Hong Kong Stock Exchange
}


def _suffix_from_exchange_id(exchange_id: str, isin: str = "") -> Optional[str]:
    """Derive Yahoo Finance suffix from DeGiro exchangeId.

    Tiebreaks ambiguous exchangeIds using ISIN country prefix:
      663 → US ISIN returns "" (bare NASDAQ), GB/IE/LU returns .L,
            unknown ISIN returns None (lets ISIN scan handle it)
      194 → IE/LU ISIN returns None (UCITS ETFs wrongly routed to Stockholm),
            genuine Swedish stocks return .ST
    """
    if not exchange_id:
        return None
    suffix = _DEGIRO_EXCHANGE_TO_YF_SUFFIX.get(str(exchange_id))
    if suffix is None:
        return None

    # Tiebreak 663: US ISIN → bare NASDAQ/NYSE ticker (no suffix)
    #               GB ISIN → .L (LSE)
    #               IE/LU ISIN → .L (LSE, USD share class)
    #               Unknown → return None so ISIN-guided scan takes over
    if str(exchange_id) == "663":
        if not isin:
            return None  # Unknown origin — let ISIN scan handle it
        prefix = isin[:2].upper()
        if prefix in ("US", "KY"):
            return ""     # NYSE/NASDAQ bare ticker / KY = Cayman-domiciled NASDAQ
        if prefix in ("GB", "IE", "LU"):
            return ".L"   # LSE listings
        return None       # Other ISIN on 663 — let scan handle it

    # Tiebreak 194 (Stockholm): only valid for genuinely Swedish stocks
    # IE/LU ISINs on exchangeId=194 are UCITS ETFs routed wrongly —
    # return None so ISIN-guided scan (.DE first for IE/LU) takes over
    if str(exchange_id) == "194":
        if isin and isin[:2].upper() in ("IE", "LU"):
            return None  # Let ISIN-guided scan handle UCITS ETFs
        return ".ST"     # Genuinely Swedish stocks

    return suffix


# Rate limiting: min seconds between yfinance requests
_YF_DELAY = 0.2
_last_yf_request = 0.0

# Global rate-limit flag: once 429 is hit, skip all suffix scanning for 60 seconds
_yf_rate_limited: bool = False
_yf_rate_limited_until: float = 0.0
_yf_rate_limited_lock = threading.RLock()

def _load_symbol_cache() -> None:
    """Load persisted resolution cache from disk into _resolution_cache.

    Also evicts any .L entries (LSE) whose yf_symbol ends in .L — these are
    stale for UCITS ETFs that should resolve to .DE (Xetra).  The .L listing
    returns GBp (pence) prices without GBp currency metadata, so the GBp safety
    net never fires, causing 100x price inflation before GBP→EUR FX conversion.
    """
    global _resolution_cache
    _load_symbol_overrides()
    try:
        if os.path.exists(_SYMBOL_CACHE_PATH):
            with open(_SYMBOL_CACHE_PATH, "r") as f:
                data = json.load(f)
            with _resolution_cache_lock:
                for key, entry in list(data.items()):
                    if isinstance(entry, dict) and entry.get("yf_symbol", "").endswith(".L"):
                        logger.info(
                            "[INFO] Evicted stale .L resolution cache entry for %s "
                            "— will re-resolve to .DE",
                            key,
                        )
                        continue  # skip = don't load .L entries
                    _resolution_cache[key] = entry
            logger.info("Loaded %d resolution cache entries from disk", len(_resolution_cache))
    except Exception as e:
        logger.warning("Could not load symbol cache: %s", e)


def _save_symbol_cache() -> None:
    """Persist current resolution cache to disk.

    Must be called with _resolution_cache_lock held, or from a context where
    no other thread may write to _resolution_cache (all resolution cache
    writers are serialized by this function).
    """
    try:
        os.makedirs(os.path.dirname(_SYMBOL_CACHE_PATH), exist_ok=True)
        with _SYMBOL_CACHE_FILE_LOCK:
            with _resolution_cache_lock:
                data = dict(_resolution_cache)
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
    global _yf_rate_limited, _yf_rate_limited_until
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

    _competing_exchanges = set()
    for cur, exc_set in currency_map.items():
        if cur != position_currency.upper():
            _competing_exchanges.update(exc_set)

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

        # Second pass: accept any exchange if no preferred-exchange match found
        for quote in quotes:
            sym = quote.get("symbol", "")
            exch = quote.get("exchange", "")
            if not sym or not exch:
                continue
            if exch in _ISIN_AS_SYMBOL_EXCHANGES:
                continue
            if len(sym) > 12:
                continue
            if exch in _competing_exchanges:
                continue  # never fall back to wrong-currency exchange
            logger.debug("ISIN %s resolved to %s via fallback exchange %s", isin, sym, exch)
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


def _resolve_yf_symbol(
    symbol: str,
    isin: str = "",
    position_currency: str = "EUR",
    exchange_id: str = "",
    evict_on_404: bool = False,
) -> str:
    """Resolve a DeGiro symbol to a yfinance-compatible ticker.

    DeGiro symbols sometimes lack exchange suffixes. We try common ones.
    Results are cached in the resolution cache (persistent, no TTL).
    On yfinance 404: if evict_on_404=True, entry is evicted and next run re-resolves.
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

    # Step -1: Check manual overrides (ISIN-keyed, highest priority — must beat cache)
    if isin:
        with _symbol_overrides_lock:
            override = _symbol_overrides.get(isin.strip().upper(), "")
        if override:
            logger.debug("Symbol override for ISIN %s: %s", isin, override)
            with _resolution_cache_lock:
                _resolution_cache[cache_key] = {
                    "yf_symbol": override,
                    "exchange": "",
                    "currency": "",
                    "method": "override",
                }
            _save_symbol_cache()
            return override

    # Check resolution cache first — return directly on hit (no re-validation call)
    with _resolution_cache_lock:
        if cache_key in _resolution_cache:
            entry = _resolution_cache.get(cache_key)
            if entry and isinstance(entry, dict):
                cached_yf = entry.get("yf_symbol", "")
                if cached_yf:
                    return cached_yf
                # Negative cache (no yf_symbol) — check if still valid
                cached_at = entry.get("cached_at", 0)
                if time.time() - cached_at < 86400:
                    return ""  # still within 24h negative cache TTL
                # Expired — evict and re-resolve
                del _resolution_cache[cache_key]

    def _cache_resolution(yf_sym: str, method: str, exchange: str = "", currency: str = "") -> str:
        """Store successful resolution in cache and return the symbol."""
        with _resolution_cache_lock:
            _resolution_cache[cache_key] = {
                "yf_symbol": yf_sym,
                "exchange": exchange,
                "currency": currency,
                "method": method,
                "cached_at": time.time(),
            }
        _save_symbol_cache()
        return yf_sym

    def _evict_and_return(empty_str: str) -> str:
        """Evict stale/404'd entry and return empty string."""
        if evict_on_404:
            with _resolution_cache_lock:
                _resolution_cache.pop(cache_key, None)
            _save_symbol_cache()
            logger.debug("Evicted resolution cache entry for %s (yfinance 404)", cache_key)
        return empty_str

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
                    return _cache_resolution(candidate, "exchange_id", suffix, "")
            except YFTickerMissingError as e:
                if "404" in str(e) or "Not Found" in str(e):
                    return _evict_and_return("")
                logger.debug("exchangeId candidate %s failed: %s", candidate, e)
            except Exception as e:
                logger.debug("exchangeId candidate %s failed: %s", candidate, e)

    # Step 0.5: For Tradegate (196) US-ISIN stocks, resolve via direct ISIN
    # lookup. DeGiro's local symbol (NVD, PTX, 6RV, O9T) is a German market
    # code that Yahoo doesn't know. yfinance 1.3.0 accepts raw ISINs as tickers
    # and returns the canonical listing (NVDA, PLTR, APP, ARM on NASDAQ).
    if exchange_id == "196" and isin and isin.upper().startswith("US"):
        try:
            _yf_throttle()
            t = yf.Ticker(isin)
            hist = t.history(period="5d")
            if not hist.empty:
                resolved = t.info.get("symbol", "")
                if resolved:
                    logger.info(
                        "Resolved Tradegate US stock %s (ISIN %s) → %s via ISIN lookup",
                        symbol, isin, resolved,
                    )
                    return _cache_resolution(resolved, "tradegate_isin", "", "USD")
        except YFTickerMissingError as e:
            if "404" in str(e) or "Not Found" in str(e):
                return _evict_and_return("")
            logger.debug("ISIN direct lookup failed for %s (%s): %s", symbol, isin, e)
        except Exception as e:
            logger.debug("ISIN direct lookup failed for %s (%s): %s", symbol, isin, e)

    # Step 0: ISIN-based resolution (most accurate — resolves ETFs/ETPs whose
    # DeGiro symbol differs from Yahoo ticker, e.g. QDVD → QDVD.L)
    if isin:
        with _yf_rate_limited_lock:
            if _yf_rate_limited and time.time() < _yf_rate_limited_until:
                logger.warning("Rate limited — skipping ISIN search for %s", symbol)
            else:
                isin_result = _resolve_by_isin(isin, position_currency)
                if isin_result:
                    return _cache_resolution(isin_result, "isin", "", position_currency)

    # European suffixes tried first so dual-listed stocks (ASML, TDIV) resolve
    # to the EUR-denominated listing before the bare symbol hits NASDAQ.
    # .HE = Helsinki (Nokia), .F = Frankfurt Xetra ETFs (alternative to .DE).
    # "" (bare) is last — only reached for genuine US-only listings.
    suffixes_to_try = _get_suffix_order(isin, symbol)
    for suffix in suffixes_to_try:
        # Fix part 3 — skip .L (LSE GBp pence listing) in suffix scan.
        # .DE is preferred for IE/LU UCITS ETFs.  .L returns GBp prices without
        # currency metadata, so the GBp safety net never fires.
        if suffix == ".L":
            continue
        with _yf_rate_limited_lock:
            if _yf_rate_limited and time.time() < _yf_rate_limited_until:
                logger.warning("Rate limited — skipping suffix scan for %s", symbol)
                return ""
        candidate = symbol + suffix
        try:
            ticker = yf.Ticker(candidate)
            _yf_throttle()
            info = ticker.info or {}
            if info.get("regularMarketPrice"):
                return _cache_resolution(candidate, "suffix_scan", suffix, "")
        except YFTickerMissingError as e:
            if "404" in str(e) or "Not Found" in str(e):
                return _evict_and_return("")
            err_str = str(e)
            if "429" in err_str or "Too Many Requests" in err_str \
                    or "Rate limited" in err_str or "YFRateLimitError" in err_str:
                with _yf_rate_limited_lock:
                    _yf_rate_limited = True
                    _yf_rate_limited_until = time.time() + 60.0
                logger.warning(
                    "Rate limit detected resolving %s — aborting suffix scan", symbol
                )
                return ""
            # Other error — continue to next suffix
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
                return ""
            # 404 or other error — continue to next suffix

    # All suffixes exhausted — cache the negative result for 24h so next run skips scan
    with _resolution_cache_lock:
        _resolution_cache[cache_key] = {
            "yf_symbol": "",
            "exchange": "",
            "currency": "",
            "method": "notfound",
            "cached_at": time.time(),
        }
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


def _infer_etf_category_from_name(name: str) -> Optional[str]:
    """Infer broad ETF category from name — fallback for UCITS ETFs yfinance doesn't classify."""
    if not name:
        return None
    n = name.lower()
    if any(k in n for k in ["bond", "fixed income", "treasury", "gilt", "aggregate", "government", "sovereign"]):
        return "Fixed Income"
    if any(k in n for k in ["real estate", "reit", "property"]):
        return "Real Estate"
    if any(k in n for k in ["gold", "silver", "commodity", "commodities"]):
        return "Commodities"
    if any(k in n for k in ["emerging market", "emerging markets", "em ucits", "msci em", "em sml"]):
        return "Emerging Markets Equity"
    if any(k in n for k in ["s&p 500", "s&p500", "msci usa", "nasdaq", "russell", "dow jones"]):
        return "US Equity"
    if any(k in n for k in ["europe", "euro stoxx", "stoxx europe", "msci europe"]):
        return "European Equity"
    if any(k in n for k in ["asia", "pacific", "japan", "china", "india", "korea"]):
        return "Asia-Pacific Equity"
    if any(k in n for k in ["clean energy", "renewable energy", "solar", "wind energy"]):
        return "Energy"
    if any(k in n for k in ["world", "global", "msci acwi", "all country", "all-world", "allworld", "ftse all", "developed market", "div lead"]):
        return "Global Equity"
    if any(k in n for k in ["tech", "technology", "semiconductor", "software", "gaming", "esport"]):
        return "Technology"
    if any(k in n for k in ["health", "healthcare", "pharma", "biotech"]):
        return "Healthcare"
    if any(k in n for k in ["financ", "bank", "insurance"]):
        return "Financials"
    if any(k in n for k in ["esg", "sustainable", "responsible", "sri"]):
        return "ESG / Sustainable"
    return None

def _infer_country_from_etf_name(name: str, category: str) -> str:
    """Infer geographic region from ETF name or category for geo chart."""
    n = (name + " " + (category or "")).lower()

    if any(k in n for k in ["world", "global", "acwi", "all-world", "allworld",
                              "ftse all", "developed market", "all country",
                              "msci world", "msci acwi"]):
        return "Global"
    if any(k in n for k in ["s&p 500", "sp500", "s&p500", "nasdaq", "us equity",
                              "united states", "usa", "north america",
                              "dow jones", "russell", "russell 2000", "us small cap"]):
        return "United States"
    if any(k in n for k in ["europe", "european", "euro stoxx", "stoxx",
                              "euronext", "ftse europe"]):
        return "Europe"
    if any(k in n for k in ["emerging", "em equity", "bric", "asia pacific",
                              "asia ex", "apac"]):
        return "Emerging Markets"
    if any(k in n for k in ["china", "chinese"]):
        return "China"
    if any(k in n for k in ["japan", "japanese", "topix", "nikkei"]):
        return "Japan"
    if any(k in n for k in ["india", "indian"]):
        return "India"
    if any(k in n for k in ["uk equity", "united kingdom", "ftse 100", "ftse100"]):
        return "United Kingdom"
    if any(k in n for k in ["germany", "german", "dax"]):
        return "Germany"
    if any(k in n for k in ["clean energy", "renewable", "solar", "wind",
                              "battery", "esg", "sustainable", "green"]):
        return "Global"  # thematic ETFs are inherently global
    if any(k in n for k in ["technology", "tech", "semiconductor", "cyber",
                              "robotics", "artificial intelligence", "ai ",
                              "gaming", "esport", "wide moat", "moat"]):
        return "Global"  # sector ETFs typically global
    if any(k in n for k in ["gold", "silver", "commodity", "commodities",
                              "oil", "energy commodity"]):
        return "Global"
    if any(k in n for k in ["glb", "gl wide", "screened"]):
        return "Global"
    return "Other"

def _get_cached_price(yf_symbol: str) -> tuple[Optional[float], Optional[str]]:
    """Check price cache for a fresh entry. Returns (price, currency) or (None, None) if missing/expired."""
    with _price_cache_lock:
        entry = _price_cache.get(yf_symbol)
        if entry and isinstance(entry, dict):
            if time.time() - entry.get("timestamp", 0) < _PRICE_CACHE_TTL:
                return entry.get("current_price"), entry.get("price_currency")
    return None, None


def _update_price_cache(yf_symbol: str, price: float, currency: str) -> None:
    """Update price cache with fresh price data."""
    with _price_cache_lock:
        _price_cache[yf_symbol] = {
            "current_price": price,
            "price_currency": currency,
            "timestamp": time.time(),
        }


def _get_cached_fundamentals(cache_key: str) -> Optional[dict]:
    """Return cached fundamentals dict if fresh (< 24h), else None."""
    with _resolution_cache_lock:
        entry = _resolution_cache.get(cache_key)
        if not entry or not isinstance(entry, dict):
            return None
        fundamentals = entry.get("fundamentals")
        if not fundamentals or not isinstance(fundamentals, dict):
            return None
        if time.time() - fundamentals.get("cached_at", 0) >= _FUNDAMENTALS_TTL:
            return None
        return fundamentals


def _update_fundamentals_cache(cache_key: str, sector: Optional[str],
                               country: Optional[str], pe_ratio: Optional[float],
                               week52_high: Optional[float], currency: str,
                               short_name: Optional[str]) -> None:
    """Update fundamentals in the resolution cache entry and persist to disk."""
    with _resolution_cache_lock:
        entry = _resolution_cache.get(cache_key)
        if not entry or not isinstance(entry, dict):
            return
        entry["fundamentals"] = {
            "sector": sector,
            "country": country,
            "pe_ratio": pe_ratio,
            "week52_high": week52_high,
            "currency": currency,
            "short_name": short_name,
            "cached_at": time.time(),
        }
    _save_symbol_cache()


def _is_cache_warm(symbol: str, isin: str) -> bool:
    """Return True if both resolution and fundamentals are fresh in cache (no yfinance call needed)."""
    cache_key = f"{symbol}:{isin}"
    with _resolution_cache_lock:
        entry = _resolution_cache.get(cache_key)
        if not entry or not isinstance(entry, dict):
            return False
        cached_yf = entry.get("yf_symbol", "")
        if not cached_yf:
            return False
        if time.time() - entry.get("cached_at", 0) >= 86400:
            return False
        fundamentals = entry.get("fundamentals")
        if not fundamentals or not isinstance(fundamentals, dict):
            return False
        if time.time() - fundamentals.get("cached_at", 0) >= _FUNDAMENTALS_TTL:
            return False
    return True


def enrich_position(position: dict, price_batch: dict | None = None) -> dict:
    """Enrich a single position with yfinance data.

    Uses two-layer caching:
    - Resolution cache (persistent, no TTL): skips ISIN/suffix/Tradegate resolution on hit
    - Price cache (in-memory, 15-min TTL): stores current_price to avoid redundant yfinance calls

    If yfinance fails for a position, affected fields are set to None.
    The position dict is updated in place and returned.

    price_batch: optional dict of {yf_symbol: price} from a batch yf.download() prefetch.
    If provided, prices are looked up here first before calling yfinance per-symbol.
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

    # Fast path: if both resolution and fundamentals are cached, skip all yfinance calls
    if _is_cache_warm(symbol, isin):
        cache_key = f"{symbol}:{isin}"
        with _resolution_cache_lock:
            entry = _resolution_cache.get(cache_key)
            if entry:
                position["sector"] = entry.get("fundamentals", {}).get("sector")
                position["country"] = entry.get("fundamentals", {}).get("country")
                position["pe_ratio"] = entry.get("fundamentals", {}).get("pe_ratio")
                yf_sym = entry.get("yf_symbol", "")
                yf_currency = entry.get("fundamentals", {}).get("currency", "EUR")
                # Derive currency from exchange suffix
                if yf_sym:
                    if "." in yf_sym:
                        suffix = "." + yf_sym.rsplit(".", 1)[-1]
                    else:
                        suffix = ""
                    _EUR_EXCH = {".AS", ".PA", ".DE", ".F", ".MI", ".MC", ".HE", ".SW"}
                    _GBP_EXCH = {".L"}
                    if suffix in _EUR_EXCH:
                        yf_currency = "EUR"
                    elif suffix in _GBP_EXCH:
                        yf_currency = "GBP"
                # Use price from batch fetch first (fresh), then fall back to stale _price_cache
                fresh_price = price_batch.get(yf_sym) if price_batch else None
                if fresh_price is None:
                    fresh_price, _ = _get_cached_price(yf_sym)
                # Always stamp price_source so it's set even if fresh_price is None
                position["price_source"] = "batch" if price_batch and yf_sym in price_batch else "cache"
                if fresh_price:
                    position["current_price"] = round(fresh_price, 4)
                    position["current_value"] = round(fresh_price * position.get("quantity", 0), 2)
                    position["currency"] = yf_currency
                    if position.get("avg_buy_price", 0) > 0:
                        position["unrealized_pl_pct"] = round(
                            ((fresh_price - position["avg_buy_price"]) / position["avg_buy_price"]) * 100, 2
                        )
                        position["unrealized_pl"] = round(
                            (fresh_price - position["avg_buy_price"]) * position.get("quantity", 0), 2
                        )
                    position["52w_high"] = entry.get("fundamentals", {}).get("week52_high")
                    position["52w_low"] = None  # not cached
        logger.info("Cache hit for %s — returning enriched from cache", symbol)
        return position

    cache_key = f"{symbol}:{isin}"
    yf_symbol = ""

    # Step 1: Check resolution cache
    with _resolution_cache_lock:
        entry = _resolution_cache.get(cache_key)
        if entry and isinstance(entry, dict):
            cached_yf = entry.get("yf_symbol", "")
            if cached_yf:
                yf_symbol = cached_yf
                cached_at = entry.get("cached_at", 0)
                if time.time() - cached_at >= 86400:
                    # 24h negative cache expired — clear and re-resolve
                    del _resolution_cache[cache_key]
                    yf_symbol = ""
                else:
                    logger.info("Resolution cache hit for %s, skipping lookup", symbol)

    # Step 2: Resolution cache miss — resolve symbol
    if not yf_symbol:
        yf_symbol = _resolve_yf_symbol(
            symbol, isin, position.get("currency", "EUR"), position.get("exchange_id", ""),
            evict_on_404=True,
        )
        if not yf_symbol:
            logger.debug("No yfinance symbol resolved for %s (ISIN: %s) — skipping enrichment", symbol, isin)
            return position

    # Step 3: Check price cache for current price
    cached_price, cached_price_currency = _get_cached_price(yf_symbol)

    # Step 4: Check fundamentals cache — skip ticker.info if fresh
    cached_fundamentals = _get_cached_fundamentals(cache_key)
    if cached_fundamentals:
        logger.info("Fundamentals cache hit for %s, skipping ticker.info", symbol)
        position["sector"] = cached_fundamentals.get("sector")
        position["country"] = cached_fundamentals.get("country")
        position["pe_ratio"] = cached_fundamentals.get("pe_ratio")
        wk52_high = cached_fundamentals.get("week52_high")
        yf_currency = cached_fundamentals.get("currency", "")
    else:
        logger.debug("Fundamentals cache miss for %s — calling ticker.info", symbol)

    try:
        ticker = yf.Ticker(yf_symbol)

        # Get info dict for fundamental data (only when fundamentals cache miss)
        if cached_fundamentals is None:
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
                # Check for 404 — evict resolution cache entry
                if "404" in err_str or "Not Found" in err_str or "not found" in err_str.lower():
                    with _resolution_cache_lock:
                        _resolution_cache.pop(cache_key, None)
                    _save_symbol_cache()
                    logger.warning("yfinance 404 for %s (%s) — evicted resolution cache", symbol, yf_symbol)
                    position["_enrichment_error"] = "yfinance_error"
                    return position
                logger.warning("ticker.info failed for %s: %s", symbol, e)
                info = {}

            # Sector — stocks use "sector"/"industry"; ETFs use "category" as proxy
            if position.get("asset_type") == "ETF":
                etf_name = info.get("longName") or info.get("shortName") or position.get("name", "")
                position["sector"] = (
                    info.get("categoryName")
                    or info.get("category")
                    or info.get("industry")
                    or _infer_etf_category_from_name(etf_name)
                )
            else:
                position["sector"] = (
                    info.get("sector")
                    or info.get("industry")
                    or None
                )

            # Country
            if position.get("asset_type") == "ETF":
                position["country"] = _infer_country_from_etf_name(
                    position.get("name", ""),
                    info.get("category", "") or ""
                )
            else:
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

            # Cache the fundamentals for future runs
            short_name = info.get("shortName", None)
            _update_fundamentals_cache(
                cache_key,
                position.get("sector"), position.get("country"),
                position.get("pe_ratio"), wk52_high,
                yf_currency, short_name,
            )
        else:
            # Fundamentals cache hit — determine currency from exchange suffix only
            _EUR_EXCHANGE_SUFFIXES = {".AS", ".PA", ".DE", ".F", ".MI", ".MC",
                                       ".HE", ".SW", ".EAM", ".EPA", ".ETR"}
            _GBP_EXCHANGE_SUFFIXES = {".L"}
            if "." in yf_symbol:
                resolved_suffix = "." + yf_symbol.rsplit(".", 1)[-1]
            else:
                resolved_suffix = ""
            if resolved_suffix in _EUR_EXCHANGE_SUFFIXES:
                yf_currency = "EUR"
            elif resolved_suffix in _GBP_EXCHANGE_SUFFIXES:
                yf_currency = "GBP"
            _price_currency_safe = True  # default when using cached fundamentals
            wk52_low = None  # not cached, will be derived from history if available

        # Store the yf-derived currency so the FX conversion block (line 1308+) uses
        # the correct price currency rather than the DeGiro-reported position currency,
        # which can be wrong (e.g. USD for EUR-denominated Xetra UCITS ETFs).
        if yf_currency:
            position["currency"] = yf_currency

        pos_currency = position.get("currency", "EUR").upper().strip()
        if yf_currency:
            _price_currency_safe = (yf_currency == pos_currency)
        # else: yf_currency unknown → keep _price_currency_safe = True (trust price)

        if not _price_currency_safe:
            logger.debug(
                "Currency mismatch for %s: exchange=%s (%s), position=%s"
                " — keeping DeGiro price, yfinance metrics retained",
                symbol, resolved_suffix or "bare", yf_currency, pos_currency,
            )

        # Get historical data for RSI and performance (always fresh — not cached)
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

            # Price: use batch prefetch first, then price cache, then per-ticker history
            yf_price = 0.0
            if price_batch is not None and yf_symbol in price_batch:
                yf_price = price_batch[yf_symbol]
            elif cached_price is not None and cached_price_currency == yf_currency and _price_currency_safe:
                # Fresh price cache hit — use cached price
                yf_price = cached_price
            else:
                # Price cache miss or stale/wrong currency — fetch from history
                _yf_throttle()
                if len(close) > 0 and _price_currency_safe:
                    yf_price = float(close.iloc[-1])

            if yf_price > 0:
                # GBp (pence) safety net: yfinance returns LSE prices in GBp (pence),
                # but fast_info.currency / info.currency correctly reports "GBp".
                # Convert pence → pounds before storing so FX conversion works correctly.
                ticker_currency = ""
                try:
                    ticker_currency = ticker.info.get("currency", "") or ""
                    if not ticker_currency:
                        ticker_currency = getattr(ticker.fast_info, "currency", "") or ""
                except Exception:
                    pass
                if ticker_currency == "GBp":
                    yf_price = yf_price / 100.0
                    yf_currency = "GBP"
                position["current_price"] = round(yf_price, 4)
                position["current_value"] = round(yf_price * position["quantity"], 2)
                position["price_source"] = "batch"
                _update_price_cache(yf_symbol, yf_price, yf_currency)
                if position["avg_buy_price"] > 0:
                    position["unrealized_pl_pct"] = round(
                        ((yf_price - position["avg_buy_price"]) / position["avg_buy_price"]) * 100, 2
                    )
                    position["unrealized_pl"] = round(
                        (yf_price - position["avg_buy_price"]) * position["quantity"], 2
                    )

        # 52w high/low and distance — only write when currencies match.
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
            # Check for 404 — evict resolution cache entry
            if "404" in err_str or "Not Found" in err_str or "not found" in err_str.lower():
                with _resolution_cache_lock:
                    _resolution_cache.pop(cache_key, None)
                _save_symbol_cache()
                logger.warning(
                    "yfinance 404 for %s (%s) — evicted resolution cache",
                    symbol, yf_symbol,
                )
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
    due to poisoned cache entries. Clears both resolution and price caches.
    """
    with _resolution_cache_lock:
        count = len(_resolution_cache)
        _resolution_cache.clear()
    with _price_cache_lock:
        _price_cache.clear()
    try:
        if os.path.exists(_SYMBOL_CACHE_PATH):
            os.remove(_SYMBOL_CACHE_PATH)
    except OSError:
        pass
    return count


def audit_symbol_cache() -> int:
    """Check resolution cache for entries that resolved to bare symbols (no exchange suffix).

    Such entries indicate the suffix scan was aborted by rate limiting before
    finding a valid suffix — they poison the cache across restarts.

    Returns the count of suspicious entries. Logs a WARNING with remediation advice.
    """
    suspicious = 0
    for key, entry in _resolution_cache.items():
        if not isinstance(entry, dict):
            continue
        yf_sym = entry.get("yf_symbol", "")
        # Bare symbol (no ".") may indicate rate-limiting abortion
        if yf_sym and "." not in yf_sym:
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

    _enrich_start = time.time()

    # Step 1: Resolve all yf_symbols first (before any yfinance calls)
    resolved_symbols: list[str] = []
    resolved_yf_symbols: list[str] = []
    symbol_to_position_idx: dict[str, list[int]] = {}

    for idx, pos in enumerate(positions):
        sym = pos.get("symbol", "")
        isin = pos.get("isin", "")
        yf_sym = ""
        cache_key = f"{sym}:{isin}"

        with _resolution_cache_lock:
            entry = _resolution_cache.get(cache_key)
            if entry and isinstance(entry, dict):
                cached_yf = entry.get("yf_symbol", "")
                if cached_yf:
                    cached_at = entry.get("cached_at", 0)
                    if time.time() - cached_at < 86400:
                        yf_sym = cached_yf

        if not yf_sym:
            yf_sym = _resolve_yf_symbol(
                sym, isin, pos.get("currency", "EUR"), pos.get("exchange_id", ""),
                evict_on_404=True,
            )

        resolved_symbols.append(yf_sym)
        resolved_yf_symbols.append(yf_sym)
        if yf_sym:
            symbol_to_position_idx.setdefault(yf_sym, []).append(idx)

    # Step 2: Batch fetch prices for all resolved symbols
    unique_yf_symbols = [s for s in dict.fromkeys(resolved_yf_symbols) if s]  # deduplicate, skip empty
    price_batch: dict[str, float] = {}
    _batch_start = time.time()
    if unique_yf_symbols:
        try:
            batch = yf.download(
                unique_yf_symbols,
                period="2d",
                auto_adjust=True,
                progress=False,
                threads=False,
            )
            if batch is not None and not batch.empty:
                close_df = batch["Close"] if "Close" in batch.columns.get_level_values(0) else None
                if close_df is None:
                    close_df = batch
                for sym in unique_yf_symbols:
                    try:
                        if isinstance(close_df, pd.DataFrame):
                            if sym in close_df.columns:
                                price = float(close_df[sym].iloc[-1])
                                if price > 0:
                                    price_batch[sym] = price
                        elif isinstance(close_df, pd.Series):
                            if sym == close_df.name:
                                price = float(close_df.iloc[-1])
                                if price > 0:
                                    price_batch[sym] = price
                    except (ValueError, TypeError, KeyError):
                        pass
        except Exception as e:
            logger.warning("Batch price fetch failed: %s", e)

    _batch_elapsed = time.time() - _batch_start
    logger.info("[INFO] Batch price fetch: %d symbols in %.1fs", len(unique_yf_symbols), _batch_elapsed)

    # Step 3: Enrich all positions in parallel using asyncio.gather
    import asyncio

    async def _enrich_one(idx: int, pos: dict) -> dict:
        """Async wrapper for enrich_position to enable parallel execution."""
        yf_sym = resolved_symbols[idx]
        pos["_resolved_yf_symbol"] = yf_sym
        loop = asyncio.get_running_loop()
        enriched_pos = await loop.run_in_executor(None, enrich_position, pos, price_batch)
        is_rl = enriched_pos.get("_enrichment_error") == "rate_limited"

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

        return _sanitize_floats(enriched_pos), is_rl

    async def _run_all() -> tuple[list[dict], bool]:
        tasks = [_enrich_one(i, pos) for i, pos in enumerate(positions)]
        results = await asyncio.gather(*tasks)
        all_enriched = [r[0] for r in results]
        any_rate_limited = any(r[1] for r in results)
        return all_enriched, any_rate_limited

    enriched, _session_rate_limited = asyncio.run(_run_all())

    elapsed = time.time() - _enrich_start
    logger.info("[INFO] Enrichment completed %d positions in %.1fs", len(positions), elapsed)

    # Diagnostic summary — log every position's computed value for deviation debugging
    total_computed = 0.0
    for r in enriched:
        sym = r.get("symbol", "?")
        qty = r.get("quantity", 0)
        price = r.get("current_price")
        value = r.get("current_value_eur") or r.get("current_value", 0)
        source = r.get("price_source", "?")
        currency = r.get("currency", "?")
        logger.info(
            f"[DIAG] {sym:8s}  qty={qty:8.4f}  price={price!s:10s}  "
            f"value={value:10.2f}  src={source}  ccy={currency}"
        )
        total_computed += value or 0
    logger.info(f"[DIAG] TOTAL COMPUTED: {total_computed:.2f} {base_currency}")

    return enriched
