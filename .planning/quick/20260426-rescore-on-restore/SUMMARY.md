---
name: 20260426-rescore-on-restore
status: complete
---

## Summary
Added re-scoring logic to `_restore_portfolio_from_snapshot()` in `app/main.py` (line 244-249). After sanitizing floats, `compute_portfolio_weights` and `compute_scores` are called on restored positions so weight/momentum_score/buy_priority_score are never `None` after restore, even if the snapshot was saved during a rate-limited session.
