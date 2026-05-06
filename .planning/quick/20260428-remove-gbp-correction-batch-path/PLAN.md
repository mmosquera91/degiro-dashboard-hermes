Remove the GBp→GBP correction block from the batch path in app/market_data.py.

The correction (lines ~1336-1343) halves all .L prices after yf.download(),
but yf.download() already returns LSE prices in GBP pounds — not GBp pence.
This causes ~50% portfolio deflation for legitimate LSE holdings (ESPO.L,
QDIV.L, GOAT.L, IUES.L, NDIA.L, SMH.L, R2US.L).

The 7 UCITS ETFs with prior pence inflation (ESP0, QDVD, VVGM, QDVF, QDV5,
VVSM, ZPRR) are already handled by fixes 1 and 3 from debfd2a (evict .L from
resolution cache, block .L in ISIN scan), so they won't appear as .L in
the batch path anyway.

Keep the GBp safety net in the ticker.info/fallback path unchanged.

Steps:
1. Remove lines 1336-1343 (the for-loop that divides .L prices by 100)
2. Verify no other .L GBp correction remains in batch path
3. Verify ticker.info/fallback GBp safety net is still present