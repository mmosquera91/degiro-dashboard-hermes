# 20260426-complete-exchange-suffix-map

Replace `_DEGIRO_EXCHANGE_TO_YF_SUFFIX` with a complete map covering all DeGiro regional exchange IDs (Hamburg, Frankfurt, Stuttgart, Berlin, Düsseldorf, Munich, etc.) so O9T (ARM/Hamburg), PTX/6RV (Frankfurt) auto-resolve without manual overrides.

## Change

- **File:** `app/market_data.py`
- **Replace:** `_DEGIRO_EXCHANGE_TO_YF_SUFFIX` dict (lines 58–95)
- **With:** Complete map including German regional exchanges (2/HM, 3/BE, 4/DU, 5/MU, 6/SG, 62/F), Nordic, Southern Europe, Canada, Asia-Pacific
- **Also:** Removed orphaned LSE/NYSE tiebreaker from `_suffix_from_exchange_id()` (now dead code after 663 is exclusively mapped to `.L`)

## Expected outcome

- O9T (ARM, Hamburg exchange_id=2) → O9T.HM
- PTX (Palantir, Frankfurt exchange_id=72) → PTX.F
- 6RV (AppLovin, Frankfurt exchange_id=72) → 6RV.F
- All German regional exchanges resolve automatically
