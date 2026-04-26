---
name: 20260426-isin-resolution-eur-strict
description: Fix ISIN resolution to prefer EUR listings and skip ISIN-as-symbol exchanges
type: quick
status: complete
date: 2026-04-26
---

## Changes Applied

**File:** `app/market_data.py`, function `_resolve_by_isin()`

**Change 1 — Remove second-pass fallback:**
- Deleted the "Second pass: any result with a real symbol (fallback)" loop that was picking USD cross-listings for EUR ETFs

**Change 2 — Blocklist ISIN-as-symbol exchanges in first pass:**
- Added `_ISIN_AS_SYMBOL_EXCHANGES = {"SG", "STU", "TDG"}` to skip Stuttgart and Tradegate which return ISIN strings as symbol
- Added `len(sym) > 12` guard to skip anything that long (ISINs are 12 chars)
- Refactored first-pass loop with explicit continue guards instead of compound condition

**Effect:** VUSA → VUSA.AS (AMS), QDVD → QDVD.AS or similar EUR listing. No USD fallback.

## Post-deploy
- [ ] DELETE /api/admin/symbol-cache
