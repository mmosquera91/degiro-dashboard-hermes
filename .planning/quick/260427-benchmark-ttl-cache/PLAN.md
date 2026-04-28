---
name: benchmark-ttl-cache
description: Add TTL cache to GET /api/benchmark endpoint
---

Add TTL cache to GET /api/benchmark to avoid hitting yfinance on every request.

## Changes to app/main.py

1. **Add module-level cache variables** after the existing `_session` dict:
   ```python
   _benchmark_cache: dict = {"series": None, "snapshots": None, "attribution": None}
   _benchmark_cache_time: float = 0.0
   _BENCHMARK_TTL: int = 3600  # 1 hour
   ```

2. **In get_benchmark()**, before the `fetch_benchmark_series()` call, check the cache:
   ```python
   import time as _time
   if _benchmark_cache["series"] is not None and \
           _time.time() - _benchmark_cache_time < _BENCHMARK_TTL:
       return {
           "snapshots": _benchmark_cache["snapshots"],
           "benchmark_series": _benchmark_cache["series"],
           "attribution": _benchmark_cache["attribution"],
       }
   ```

3. **After successful fetch**, populate the cache (populate the snapshots list that was already built):
   ```python
   _benchmark_cache["series"] = benchmark_series
   _benchmark_cache["snapshots"] = [...]   # the snapshots list already built
   _benchmark_cache["attribution"] = attribution
   _benchmark_cache_time = _time.time()
   ```

4. **Invalidate cache on snapshot save** in `get_portfolio()` — after enrichment, reset `_benchmark_cache_time = 0.0` so the chart reflects new data immediately.
