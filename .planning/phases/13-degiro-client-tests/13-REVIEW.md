---
phase: 13-degiro-client-tests
reviewed: 2026-05-04T00:00:00Z
depth: standard
files_reviewed: 2
files_reviewed_list:
  - tests/test_degiro_client.py
  - app/degiro_client.py
findings:
  critical: 0
  warning: 2
  info: 0
  total: 2
status: issues_found
---

# Phase 13: Code Review Report

**Reviewed:** 2026-05-04
**Depth:** standard
**Files Reviewed:** 2
**Status:** issues_found

## Summary

Both files are well-structured and the implementation correctly handles the DeGiro key-value list format for portfolio and cash fund data. Tests are comprehensive and cover edge cases including empty inputs, missing fields, and error conditions. Two minor issues were found: dead/computed-but-unused variables in the production code and a minor test coverage gap for an edge case in `_kv_list_to_dict` that is not exercised by the current test data.

## Warnings

### WR-01: Unused computed variables in fetch_portfolio

**File:** `app/degiro_client.py:707-709`
**Issue:** Three variables are initialized with defaults but their values are overwritten by `_safe_float` calls, and then they are never used in the returned result dict (lines 914-919). Specifically:

```python
# Line 707-709 (initialization — these get overwritten below)
total_deposit_withdrawal_val = 0.0
total_cash_val = 0.0
total_fees_val = 0.0

# Line 910-912 (actual computed values)
total_deposit_withdrawal = _safe_float(total_portfolio_flat.get("totalDepositWithdrawal"))
total_cash = _safe_float(total_portfolio_flat.get("totalCash", 0))
total_fees = _safe_float(total_portfolio_flat.get("totalNonProductFees", 0))
total_deposit_withdrawal_val = total_deposit_withdrawal  # assigned but never used in result
```

The result dict (lines 914-919) only includes `positions`, `cash_available`, `currency`, and `total_deposit_withdrawal`. `total_cash_val` and `total_fees_val` are computed but discarded, and `total_cash` is also never placed in the result.

**Fix:** Either include `total_cash` and `total_fees` in the result dict, or remove the dead variable assignments to reduce noise.

---

### WR-02: Test coverage gap for None-value items in _kv_list_to_dict

**File:** `tests/test_degiro_client.py:60-70`
**Issue:** `test_kv_list_to_dict_invalid_items` tests that items missing "name" or "value" keys are skipped, but the test data does not include an item like `{"name": None, "value": 2}`. The production code's condition `if isinstance(item, dict) and "name" in item and "value" in item` checks key **existence**, not value **truthiness** — so an item with `{"name": None, "value": 2}` would pass the filter and produce an entry with `None` as the key.

Similarly, `test_non_list_input` covers string, None, and int inputs but does not test `{"name": None, "value": 2}` as a dict input.

**Fix:** Add a test case with `{"name": None, "value": 2}` to either `test_kv_list_to_dict_invalid_items` or `test_non_list_input` (if a dict is passed), asserting that it is skipped or returns `{}` respectively.

Note: This is a test gap only. In practice, `_kv_list_to_dict` is called on data from DeGiro's API where items always have non-None string values for "name" and "value", so this edge case does not affect runtime behavior.

---

_Reviewed: 2026-05-04_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_