# Quick: Fix 429 abort in _resolve_yf_symbol

## Bug
The string-based 429 detection in `_resolve_yf_symbol` fails to trigger the break because yfinance internally catches/re-raises the 429 exception, so `str(e)` does not contain "429". The loop keeps iterating suffixes: ESP0 → ESP0.AS → ESP0.PA → ... all returning 429.

## Fix

### 1. Add module-level rate-limit flag (after line 26)
```python
_yf_rate_limited: bool = False
_yf_rate_limited_lock = threading.RLock()
```

### 2. Modify `_resolve_yf_symbol` — check flag before each suffix
At the top of the `for suffix in suffixes_to_try:` loop (line 132), add:
```python
with _yf_rate_limited_lock:
    if _yf_rate_limited:
        logger.warning(
            "Rate limited — skipping suffix scan for %s", symbol
        )
        return symbol
```

### 3. In exception handler — set flag and return (line 144)
After detecting 429 via string match, set the global flag:
```python
with _yf_rate_limited_lock:
    _yf_rate_limited = True
logger.warning(
    "Rate limit detected resolving %s — aborting all "
    "further symbol resolution this session", symbol
)
return symbol
```

### 4. In `enrich_positions` — reset flag at start (line 352)
At the start of `enrich_positions`, add:
```python
global _yf_rate_limited
with _yf_rate_limited_lock:
    _yf_rate_limited = False
```

## Scope
- Only `app/market_data.py`
- Do NOT change `enrich_position` (single) or `_yf_throttle`

## Verification
- When Yahoo returns 429 on suffix[i], no further suffixes are tried for that symbol
- When Yahoo returns 429 on symbol X, no suffix scanning occurs for X+1..N
- Log shows "Rate limit detected" exactly once per 429 encounter
- On next `enrich_positions` call, flag resets and resolution resumes
- `tests/test_market_data.py` passes
