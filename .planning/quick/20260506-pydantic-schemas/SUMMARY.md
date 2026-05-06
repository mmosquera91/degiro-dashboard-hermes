---
name: "20260506-pydantic-schemas"
description: "Add Pydantic schemas for all API endpoints"
type: "quick"
status: "complete"
---

## What was done

- **Created `app/schemas.py`** — all request/response BaseModels:
  - `AuthRequest`, `SessionRequest` (request bodies)
  - `HealthResponse`, `AuthResponse`, `PortfolioResponse`, `BenchmarkResponse`,
    `SnapshotSaveResponse`, `SnapshotDeleteResponse`, `EnrichmentStatusResponse`,
    `HermesContextResponse`, `SessionTokenResponse`
  - Plus supporting: `RefreshPricesResponse`, `SymbolCacheClearResponse`,
    `ReloadOverridesResponse`, `LogoutResponse`, `SnapshotListItem`, `SnapshotListResponse`

- **Updated `app/main.py`** — removed inline BaseModels, imported all schemas,
  added `response_model=` to every route:
  - `GET /health` → `HealthResponse`
  - `POST /api/auth` → `AuthResponse`
  - `POST /api/session` → `AuthResponse`
  - `GET /api/portfolio` → `PortfolioResponse`
  - `POST /api/refresh-prices` → `RefreshPricesResponse`
  - `GET /api/enrichment-status` → `EnrichmentStatusResponse`
  - `GET /api/hermes-context` → `HermesContextResponse`
  - `GET /api/session-token` → `SessionTokenResponse`
  - `POST /api/logout` → `LogoutResponse`
  - `DELETE /api/admin/symbol-cache` → `SymbolCacheClearResponse`
  - `POST /api/admin/reload-overrides` → `ReloadOverridesResponse`
  - `GET /api/benchmark` → `BenchmarkResponse`
  - `GET /api/snapshots` → `SnapshotListResponse`
  - `DELETE /api/snapshots/{date_str}` → `SnapshotDeleteResponse`
  - `POST /api/snapshots/save` → `SnapshotSaveResponse`

- **Created `DECISIONS.md`** at repo root — documents `network_mode: host`
  decision with pros/cons, mitigation for non-Linux environments.

- **Tested in Docker** — `docker exec brokr bash -c 'PYTHONPATH=/app pytest tests/ --ignore=/app/tests/test_degiro_client.py -q'`:
  **218 passed, 3 failed** (pre-existing failures in `test_market_data.py`
  `TestEnrichPositionExceptionHandling` — `_enrichment_error` key not present;
  not related to this change).

## Commit

`8bf5617` — `feat(api): add Pydantic schemas for all request/response models`
