---
name: 260428-revert-wrong-bundled-overrides
description: Revert bundled_overrides.json to only known-correct SXRU.DE override
status: complete
---

## Summary

- Removed 7 wrong AMS tickers from `app/bundled_overrides.json`: ESPO.AS, QDIV.AS, GOAT.AS, IUES.AS, NDIA.AS, SMH.AS, R2US.AS
- Kept only the known-correct override: `{"IE00B53L4350": "SXRU.DE"}`
- Committed as `77bb48f` and pushed to origin/master

## Post-push actions required (manual)

1. `DELETE /api/admin/symbol-cache`
2. Run "Update Prices" to restore previous working state (DeGiro prices used for these 7, RSI/metrics missing but values correct)
