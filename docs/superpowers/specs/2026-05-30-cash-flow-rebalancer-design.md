# Design — Cash-Flow Rebalancing Planner (Feature A)

*Drafted 2026-05-30. Status: design, pending user review → implementation plan.*
*Roadmap context: `docs/ROADMAP-portfolio-health.md` (feature A, flagship).*

## Mission

A long-term owner practicing **"mostly buy, rarely sell"** periodically adds cash and
asks: *"Where should my next €X go?"* The planner answers with a **buy-only** allocation
that steers the portfolio back toward its targets. It never proposes a sell — rebalancing
happens purely by directing new contributions. This is the literal embodiment of the
project mission.

## Scope (v1)

**In:**
- A new pure module, `app/rebalance.py`, that takes the existing enriched portfolio dict +
  a cash amount and returns a buy plan.
- One read endpoint: `GET /api/rebalance-plan?amount=<eur>`.
- A dashboard panel: amount input → ordered buy list + leftover/hold reserve + rationale.
- Plan included in the Hermes export so the AI agent reasons with it.

**Out (v1):**
- Buying **new** positions not already owned → deferred to feature B (watchlist). v1 tops
  up **owned positions only**. The module is structured so a watchlist candidate source
  plugs in later without redesign.
- Placing orders. Brokr never trades; it advises. Output is a plan the user executes in
  DeGiro manually.
- Persisting plans. Plans are computed on demand and ephemeral, like benchmark data.

## Decisions (resolved with user)

| # | Decision | Choice |
|---|----------|--------|
| D1 | Output form | **Both** — compute ideal notional split, snap to whole shares, show leftover cash |
| D2 | Objective | **Drift-then-rank** — correct allocation/sector/concentration first; break ties by `buy_priority_score` |
| D3 | Over-budget / poor candidates | **Hold reserve** — deploy what improves health/quality; flag the rest as "hold" with a reason |
| D4 | Buy universe | **Owned positions only** in v1; watchlist (B) plugs in later |

## Inputs

The planner consumes the **already-enriched** portfolio dict held in `_session["portfolio"]`
(or restored from snapshot) — the same object `/api/portfolio` returns. No DeGiro call, no
new enrichment. Required fields **already present** on each position:

- `asset_type` (`"ETF"` | `"STOCK"`), `current_value_eur`, `weight`, `current_price`,
  `currency`, `quantity`, `buy_priority_score`, `buy_priority_blocked_reason`, `sector`,
  `name`, `symbol`, `isin`.

Portfolio-level: `total_value_eur`, `etf_allocation_pct`, `stock_allocation_pct`,
`sector_breakdown`, `cash_available`.

Config (env, reuse existing): `TARGET_ETF_PCT`, `TARGET_STOCK_PCT`,
`HEALTH_POSITION_THRESHOLD` (concentration cap), `HEALTH_SECTOR_THRESHOLD` (sector cap).

**FX note:** `current_price` is in the position's local `currency`; `current_value_eur` is
already FX-normalized. To convert a EUR budget slice into a whole-share count we need the
per-share EUR price = `current_value_eur / quantity` (avoids re-fetching FX — derive it
from values the portfolio already carries). Positions flagged `fx_missing` or with
`quantity == 0` / missing price are **excluded** from buying and listed under `excluded`.

## Algorithm

A pure function: `plan_contribution(portfolio: dict, amount_eur: float) -> RebalancePlan`.

### Step 1 — Target the under-weighted asset class
Compute post-contribution drift. Determine how much of the new cash each side (ETF / STOCK)
should receive to move allocation toward `TARGET_ETF_PCT` / `TARGET_STOCK_PCT`. With
`total = total_value_eur` and target ETF fraction `t`:

```
desired_etf_value_after = (total + amount) * t
etf_gap = max(0, desired_etf_value_after - current_etf_value)
stock_gap = max(0, desired_stock_value_after - current_stock_value)
```

Split `amount` across the two sides proportionally to their gaps (capped so neither side
overshoots its target). If both gaps are ~0 (already at target), split by target weights so
contributions preserve the allocation.

### Step 2 — Rank candidates within each side (drift-then-rank)
Within each side's budget, rank owned positions by a priority that encodes the mission:

1. **Concentration guard (hard):** never push a position above `HEALTH_POSITION_THRESHOLD`.
   A buy that would breach the cap is truncated at the cap; excess flows to the next candidate.
2. **Sector relief (soft):** down-weight positions whose `sector` already exceeds
   `HEALTH_SECTOR_THRESHOLD`; up-weight under-represented sectors.
3. **Entry quality (tie-break):** order remaining capacity by `buy_priority_score`
   (desc). Positions with `buy_priority_score is None` (failed quality gates) are
   **deprioritized** — eligible only if no gated candidate remains, and then surfaced as a
   warning (feeds D3 hold-reserve logic).

Produces an ordered list of `(position, target_eur)` per side.

### Step 3 — Snap to whole shares (D1)
For each `(position, target_eur)`, in priority order:

```
price_eur = current_value_eur / quantity        # per-share EUR
shares    = floor(target_eur / price_eur)
spend     = shares * price_eur
```

Track running `remaining = amount - Σ spend`. After the first pass, do a **greedy
top-up**: walk the priority list again and buy one more share wherever `price_eur <=
remaining` and the concentration cap still holds, until no affordable share fits. This
minimizes leftover cash without overshooting drift targets.

### Step 4 — Hold reserve (D3)
Whatever cannot be deployed into a *health-improving, quality-passing* buy becomes the
**hold reserve**, each euro tagged with a reason:
- `"leftover"` — too small to buy another whole share of any sensible candidate.
- `"all-candidates-overbought"` — remaining candidates all failed quality gates; not forcing
  a bad entry.
- `"target-reached"` — buying more would overshoot allocation targets with no relief benefit.

The plan **always reconciles**: `Σ spend + hold_reserve == amount` (to the cent).

## Output contract

```jsonc
{
  "amount_requested": 1000.00,
  "currency": "EUR",
  "buys": [
    {
      "name": "Vanguard FTSE All-World",
      "symbol": "VWCE.DE", "isin": "IE00BK5BQT80",
      "asset_type": "ETF",
      "shares": 3, "price_eur": 118.42, "spend_eur": 355.26,
      "notional_target_eur": 360.00,          // pre-snap ideal (D1)
      "reason": "ETF underweight by 6.1pp; buy_priority 0.71",
      "new_weight_pct": 14.2                   // projected post-buy
    }
  ],
  "hold_reserve_eur": 41.30,
  "hold_reasons": [ {"amount_eur": 41.30, "reason": "leftover"} ],
  "projected": {
    "etf_allocation_pct": 69.4, "stock_allocation_pct": 30.6,
    "etf_drift_before": 6.1, "etf_drift_after": 0.6
  },
  "excluded": [ {"name": "...", "reason": "fx_missing"} ],
  "warnings": [ "All STOCK candidates are overbought — €120 held in reserve" ]
}
```

`projected` lets the UI and the AI show the **before → after** drift, making the plan's
value legible ("this moves you from 6.1pp off to 0.6pp off").

## Components & boundaries

| Unit | Responsibility | Depends on |
|------|---------------|------------|
| `app/rebalance.py` | Pure planning logic; no I/O, no network | stdlib + the portfolio dict shape |
| `GET /api/rebalance-plan` (`main.py`) | Read `_session["portfolio"]`, call planner, return plan | `rebalance.py`, auth dep |
| `schemas.py` | `RebalancePlanResponse` Pydantic model | — |
| Dashboard panel (`app.js`/`index.html`/`style.css`) | Amount input → render plan | the endpoint |
| `context_builder.py` | Add a "SUGGESTED ALLOCATION OF NEW CASH" block | calls `rebalance.py` with a default amount |

Keeping `rebalance.py` **pure** (portfolio dict + amount in, plan out) makes it directly
unit-testable with fabricated portfolios — no DeGiro, no yfinance, no session — matching how
`scoring.py` and `health_checks.py` are already tested.

## API design

```
GET /api/rebalance-plan?amount=1000
  → 200 RebalancePlanResponse
  → 400 if amount missing / <= 0 / non-numeric
  → 200 with empty buys + full hold_reserve if no portfolio loaded
        (message: "No portfolio loaded")
```

Read-only GET, bearer-auth via existing `Depends(verify_brok_token)`. No operation lock
needed — it only **reads** the cached portfolio and computes; it never mutates session
state or calls upstreams. (Contrast `/api/portfolio`, which locks because it enriches.)

## Hermes export integration

Add a section to `context_builder.py` plaintext + JSON: **"SUGGESTED ALLOCATION OF NEW
CASH."** Use `cash_available` as the default amount if > 0, else a configurable
`DEFAULT_CONTRIBUTION_EUR`. This keeps the export the product's reasoning surface — the AI
sees not just the data but a concrete buy-only plan it can endorse or refine, fully
consistent with the existing "do not recommend selling" instruction.

## Error handling & edge cases

- **No portfolio loaded** → 200, empty buys, hold = full amount, clear message.
- **amount ≤ 0 or non-numeric** → 400.
- **Single position > concentration cap already** → it receives €0; cash flows elsewhere;
  warning emitted.
- **All candidates fail quality gates** → hold reserve with `all-candidates-overbought`.
- **Tiny budget** (< cheapest share) → entire amount to hold reserve, `leftover` reason.
- **`total_value_eur == 0`** (empty portfolio) → 200, hold = full amount (nothing to top up
  in v1; B will handle from-scratch building).
- **`fx_missing` / `quantity==0` / no price** → excluded list, never bought.
- **Float safety** → reuse `_sanitize_floats` before returning, per existing convention.

## Testing strategy

Mirror `tests/test_scoring.py` / `tests/test_health_checks.py` — pure-function tests with
fabricated portfolio dicts. Cases:

1. Underweight ETFs → cash skews to ETF side; projected drift shrinks.
2. At target → cash split by target weights; allocation preserved.
3. Concentration cap → over-cap position gets €0; warning present.
4. Sector over threshold → down-weighted vs an under-represented peer.
5. Whole-share snap → `shares == floor`, `Σ spend + hold == amount` to the cent.
6. Greedy top-up → leftover < cheapest affordable share.
7. All candidates gated → full hold reserve, correct reason.
8. No portfolio / amount ≤ 0 / empty portfolio → documented responses.
9. `fx_missing` excluded and reconciliation still balances.

## Why this is safe to build now

- **Pure, additive, read-only.** New module + one GET + one UI panel. Touches no existing
  calculation; `scoring.py`, `health_checks.py`, enrichment, and the session/lock model are
  unchanged.
- **Reuses existing data and config.** No new upstream calls, no new env beyond an optional
  default-contribution knob.
- **Ships A independently of B.** The owned-only universe means A delivers value alone, and
  the candidate-source seam is already drawn for when B lands.
