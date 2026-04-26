---
name: 20260426-rescore-on-restore
description: Re-score positions after restoring from snapshot so weight/momentum_score/buy_priority_score are never None after restore
status: complete
---

## Problem
`_restore_portfolio_from_snapshot()` loads position dicts verbatim from disk. If the snapshot was saved during a rate-limited session, `weight`/`momentum_score`/`buy_priority_score` are all `None`. They stay `None` until the next full `/api/portfolio` call.

## Change
In `app/main.py`, inside `_restore_portfolio_from_snapshot()`, after the existing `_sanitize_floats` loop and before `with _session_lock:`, add:

```python
if portfolio_data.get("positions"):
    try:
        portfolio_data["positions"] = compute_portfolio_weights(portfolio_data["positions"])
        portfolio_data["positions"] = compute_scores(portfolio_data["positions"])
        logger.info("Re-scored %d restored positions from snapshot", len(portfolio_data["positions"]))
    except Exception as e:
        logger.warning("Could not re-score restored positions: %s", e)
```

`compute_portfolio_weights` and `compute_scores` are already imported at the top of `main.py` (line 20).

## Verification
- Syntax check with `python -m py_compile app/main.py`
- Change is localized to `_restore_portfolio_from_snapshot()` only
