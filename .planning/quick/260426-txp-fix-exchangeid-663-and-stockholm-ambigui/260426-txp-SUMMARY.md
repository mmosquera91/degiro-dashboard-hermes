---
name: "260426-txp"
description: "fix exchangeId 663 and Stockholm ambiguity for US stocks and IE/LU ETFs"
type: "quick"
status: "complete"
completed: "2026-04-26"
---

# Summary

## Changes Made

### app/market_data.py — _suffix_from_exchange_id() tiebreakers

Replaced the bare `_DEGIRO_EXCHANGE_TO_YF_SUFFIX.get()` with ISIN-aware tiebreakers:

**exchangeId=663 (LSE/NYSE/NASDAQ ambiguity):**
- `US*` ISIN → `""` (bare NASDAQ/NYSE ticker) — correct for AMZN, SYM, PANW, CRWV
- `GB/IE/LU*` ISIN → `".L"` (LSE) — correct for UK/Irish funds on LSE
- Unknown ISIN or no ISIN → `None` — lets ISIN-guided scan take over

**exchangeId=194 (Stockholm for genuine Swedish stocks only):**
- `IE/LU*` ISIN → `None` — UCITS ETFs (ESP0, QDVD, VVGM, QDV5) wrongly routed to Stockholm; now fall through to ISIN scan which starts with .DE
- `SE*` or no ISIN → `".ST"` — genuine Swedish stocks unchanged

### app/market_data.py — _resolve_yf_symbol() guard

The exchangeId candidate block (lines ~422-442) now checks `if suffix is not None:` before attempting resolution. When `_suffix_from_exchange_id()` returns `None` (ambiguous cases), the exchangeId step is skipped entirely and execution falls through to ISIN search + suffix scan.

## Verification

```
663 + US ISIN: ''      ✓
663 + GB ISIN: '.L'    ✓
663 + IE ISIN: '.L'    ✓
663 + LU ISIN: '.L'    ✓
663 + unknown: None    ✓
663 + no isin: None    ✓
194 + IE ISIN: None    ✓ (UCITS ETFs skip Stockholm)
194 + LU ISIN: None    ✓
194 + SE ISIN: '.ST'   ✓
194 + no isin: '.ST'   ✓
72 (Frankfurt): '.F'   ✓
645 (Xetra): '.DE'     ✓
676 (NASDAQ): ''       ✓
```

## Effect After Cache Clear

- **AMZN, SYM, PANW, CRWV** (exchangeId=663, US ISIN) → `""` suffix → bare NASDAQ ticker resolves with USD currency from `prod.get("currency")`
- **ESP0, QDVD, VVGM, QDV5** (exchangeId=194, IE/LU ISIN) → `None` from `_suffix_from_exchange_id` → ISIN scan starts with `.DE` → ESP0.DE, QDVD.DE resolve correctly
