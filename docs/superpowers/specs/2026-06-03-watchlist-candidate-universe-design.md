# Feature B — Watchlist / Candidate Universe — Design

*Drafted 2026-06-03. Status: approved design, ready for implementation planning.*

Roadmap reference: `docs/ROADMAP-portfolio-health.md` §B. Second item in the committed
A → B → C → D track. Feature A (cash-flow rebalancer) shipped; B retroactively strengthens
it by letting buy candidates include *new* names, not just top-ups.

## Goal & scope

Track tickers the user does **not** own yet, enrich and score them in the **same ETF/STOCK
pool** as owned holdings so "buy a new name" vs "top up an existing one" is directly
comparable (`buy_priority_score` apples-to-apples).

**In scope this phase:** persistent watchlist store, ISIN-based add flow, enrichment,
shared-pool scoring, a watchlist UI panel, tagging of watchlist names in the existing
top-candidates list and rebalancer panel, Hermes export, and README documentation.

**Out of scope this phase (deferred):**
- The rebalancer optimizer *actively allocating cash* to open new positions. Watchlist
  names appear in the rebalancer's ranking tagged "not owned," but the cash-allocation math
  (drift correction among owned holdings) is unchanged. Wiring the optimizer to open new
  positions changes how a 0-weight target interacts with sector/concentration drift and is a
  focused follow-up.
- Any asset type other than ETF / STOCK.

## Decisions (resolved during brainstorming)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Scoring model | **Shared pool** with owned positions | Makes "new vs top-up" directly comparable; unblocks A's full value |
| Identifier & add | **ISIN-first, pasted in UI** | Matches how positions/snapshots are keyed; reuses ISIN→yf resolution |
| Persistence | **`watchlist.json`** on data volume | Mirrors `symbol_overrides.json` (lock + load/save) |
| Asset type | **Auto-detect via yfinance `quoteType`, manual override** | Lowest friction; override guards misclassification |
| UI surface | **Dedicated panel + tagged in candidates + tagged in rebalancer** | Full payoff: ranked new names beside top-ups |
| Rebalancer depth | **Eligible + display-tagged only this phase** | Keeps B shippable and A's tested logic intact |
| Weight factor for 0-weight names | **Neutral 0.5** | A candidate earns its rank on merit, not for being unowned |

## Data model — `watchlist.json`

Mirrors the `symbol_overrides.json` pattern: env-configurable path `WATCHLIST_PATH`
(default `/data/watchlist.json`), loaded and saved under a lock.

```json
{
  "version": 1,
  "items": [
    {
      "isin": "US0378331005",
      "symbol": "AAPL",
      "name": "Apple Inc.",
      "asset_type": "STOCK",
      "asset_type_source": "auto",
      "note": "",
      "added_at": "2026-06-03"
    }
  ]
}
```

`symbol`, `name`, and `asset_type` are resolved **once at add-time** and persisted, so
ongoing refreshes do not re-run ISIN resolution.

## Add flow (resolve + classify once)

On add of an ISIN:

1. Reject if the ISIN is already owned (check current portfolio) or already on the watchlist.
2. `_resolve_by_isin(isin)` (`market_data.py:274`) → yf ticker. If it returns empty
   (not found / rate-limited), reject with a clear, user-facing error.
3. Fetch yfinance `quoteType` → `ETF` for `"ETF"`, else `STOCK`. Store as `asset_type`
   with `asset_type_source: "auto"`.
4. Persist the entry. The UI shows the detected type with an override toggle, which sets
   `asset_type` and `asset_type_source: "manual"`.

## Enrichment

Build position-like dicts from watchlist entries with `quantity: 0`, `weight: 0`,
`owned: False`, `source: "watchlist"`, and run them through the existing `enrich_position`
path (`market_data.py:1159`), reusing the 1y batch history download. This yields the same
RSI / perf / 52w / P-E / sector fields used for owned positions.

## Scoring (shared pool)

In `compute_scores` (`scoring.py:147`), watchlist dicts join the ETF and STOCK pools. All
factors z-score normally across the merged pool — value, momentum, distance-from-52w-high,
RSI — which is the intended merit comparison. Two special-cases:

- **Weight factor (20%):** compute the weight z-score over *owned* positions only, then
  assign watchlist items the neutral `0.5` directly. This prevents a 0-weight (unowned) name
  from auto-maxing the "most underweight" factor, and prevents the watchlist entries from
  distorting owned positions' weight normalization.
- **`is_buyable` gates** (`scoring.py:110`) apply identically: a watchlist STOCK that is
  overbought (RSI ≥ 70, etc.) is blocked from a buy-priority score; ETFs remain exempt.
  Consistent with how owned holdings are treated.

`get_top_candidates` (`scoring.py:328`) includes watchlist items, each tagged `owned: False`
so the UI can mark them.

## API (mirrors existing `/api/*` auth + rate-limit pattern)

- `GET /api/watchlist` → list of entries with enriched signals + scores.
- `POST /api/watchlist` → add by ISIN (runs the add flow).
- `DELETE /api/watchlist/{isin}` → remove an entry.
- `PATCH /api/watchlist/{isin}` → override `asset_type`.

New Pydantic request/response schemas in `schemas.py`.

## UI (CSP-compliant — external `/static` JS only, no inline)

- **Watchlist panel:** an ISIN add input that, on add, shows the detected asset type with an
  override toggle; below it, a list of tracked names with their enriched signals,
  `buy_priority_score`, and a remove control.
- Watchlist names appearing in the existing **top-candidates list** and **rebalancer panel**
  carry a "Watchlist / not owned" tag.

Per the CSP constraint, all client JS lives in external `/static` files (no inline JS,
no Google Fonts).

## Hermes export

Per the cross-cutting rule (the export is the product's AI reasoning surface),
`context_builder.py` gains a watchlist section listing candidate new buys with their
signals/scores, so the agent reasons about new positions alongside owned ones.

## README

`README.md` is updated to document the watchlist feature:
- **What Brokr Does** — mention the candidate universe.
- **Scoring System** — note that watchlist candidates share the ETF/STOCK pool and the
  neutral-0.5 weight-factor rule for unowned names.
- **API** — the four `/api/watchlist` endpoints.
- **Environment Variables** — `WATCHLIST_PATH`.

## Testing

- **Scoring:** a watchlist item gets neutral `0.5` on the weight factor; owned positions'
  weight normalization is unchanged when watchlist items are present in the pool;
  `is_buyable` gates apply to watchlist stocks (overbought stock blocked, ETF exempt).
- **Store:** add / remove / dedup-vs-owned / dedup-vs-watchlist; manual `asset_type`
  override persists across reload.
- **Add flow:** unresolvable ISIN rejected cleanly; `quoteType` → `asset_type` mapping
  (`"ETF"` → ETF, otherwise STOCK).

## Key code anchors

- `market_data.py:274` `_resolve_by_isin` — ISIN → yf ticker.
- `market_data.py:1159` `enrich_position` — per-symbol enrichment, works from `{symbol, isin}`.
- `scoring.py:147` `compute_scores` — pool z-scoring; weight factor to special-case.
- `scoring.py:328` `get_top_candidates` — candidate surfacing.
- `market_data.py:53` `symbol_overrides.json` load/save — persistence pattern to mirror.
- `context_builder.py` — Hermes export reasoning surface.
