---
name: "260426-txp"
description: "fix exchangeId 663 and Stockholm ambiguity for US stocks and IE/LU ETFs"
type: "quick"
status: "in-progress"
created: "2026-04-26"
agent_mode: "quick"
model: "sonnet"
---

# Plan

## Task 1: Fix _suffix_from_exchange_id() tiebreakers for 663 and 194

**File:** `app/market_data.py`

**Action:** Replace `_suffix_from_exchange_id()` with the ISIN-aware version that:
1. Returns `""` (bare NASDAQ ticker) for US ISINs on exchangeId=663
2. Returns `".L"` for GB/IE/LU ISINs on exchangeId=663
3. Returns `None` for unknown ISINs on exchangeId=663 (lets ISIN scan handle it)
4. Returns `None` for IE/LU ISINs on exchangeId=194 (lets ISIN scan handle it — UCITS ETFs)
5. Returns `".ST"` for genuine Swedish stocks on exchangeId=194

**Verify:** `python -c "from app.market_data import _suffix_from_exchange_id; print(_suffix_from_exchange_id('663','US123456789'))"` → `''`

---

## Task 2: Skip exchangeId step when suffix is None in _resolve_yf_symbol()

**File:** `app/market_data.py`

**Action:** Wrap the exchangeId candidate block (lines ~390-409) with `if suffix is not None:` guard. When `_suffix_from_exchange_id` returns None, skip the exchangeId step and fall through directly to ISIN search + suffix scan.

**Verify:** `python -c "from app.market_data import _resolve_yf_symbol; print(_resolve_yf_symbol('ESP0','IE00BKM4GZ80','EUR','194'))"` → resolves via ISIN scan

---

## must_haves

- [ ] `_suffix_from_exchange_id("663", "US...")` returns `""`
- [ ] `_suffix_from_exchange_id("663", "IE...")` returns `".L"`
- [ ] `_suffix_from_exchange_id("663", "XX...")` returns `None`
- [ ] `_suffix_from_exchange_id("194", "IE...")` returns `None`
- [ ] `_suffix_from_exchange_id("194", "SE...")` returns `".ST"`
- [ ] `_resolve_yf_symbol()` skips exchangeId block when suffix is None
- [ ] No regressions on existing exchangeId resolutions
