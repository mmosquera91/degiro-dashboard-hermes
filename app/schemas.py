"""Pydantic request/response schemas for all API endpoints."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, RootModel, ConfigDict


# ─── Request Models ────────────────────────────────────────────────────────────


class AuthRequest(BaseModel):
    username: str
    password: str
    otp: str | None = None


class SessionRequest(BaseModel):
    session_id: str
    int_account: int | None = None


# ─── Response Models ───────────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    status: str


class AuthResponse(BaseModel):
    status: str


class ErrorResponse(BaseModel):
    detail: str


class SessionTokenResponse(BaseModel):
    token: str


class EnrichmentStatusResponse(BaseModel):
    enriching: bool
    last_enriched_at: str | None


class PortfolioResponse(BaseModel):
    date: str
    total_value: float
    total_value_eur: float
    total_invested: float
    unrealized_pl_total: float | None
    unrealized_pl_total_pct: float | None
    true_total_pl: float | None
    true_total_pl_pct: float | None
    total_deposit_withdrawal: float
    etf_allocation_pct: float
    stock_allocation_pct: float
    num_positions: int
    top_5_winners: list[dict[str, Any]]
    top_5_losers: list[dict[str, Any]]
    sector_breakdown: dict[str, float]
    cash_available: float
    daily_change_pct: float | None
    daily_change_eur: float | None
    positions: list[dict[str, Any]]
    top_candidates: dict[str, list[dict[str, Any]]]
    top5_holdings: list[dict[str, Any]]
    health_alerts: list[dict[str, Any]]
    last_enriched_at: str | None


class BenchmarkResponse(BaseModel):
    snapshots: list[dict[str, Any]]
    benchmark_series: list[dict[str, Any]]
    attribution: list[dict[str, Any]]
    message: str | None = None


class SnapshotSaveResponse(BaseModel):
    saved: str


class SnapshotDeleteResponse(BaseModel):
    deleted: str


class RefreshPricesResponse(BaseModel):
    status: str


class SymbolCacheClearResponse(BaseModel):
    cleared: int


class ReloadOverridesResponse(BaseModel):
    status: str


class LogoutResponse(BaseModel):
    status: str


class SnapshotListItem(BaseModel):
    date: str
    total_value_eur: float | None
    total_invested: float | None = None
    unrealized_pl_total: float | None = None
    benchmark_value: float | None
    benchmark_return_pct: float | None
    has_portfolio_data: bool


class SnapshotListResponse(RootModel[list[SnapshotListItem]]):
    pass


class HermesContextResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    json: dict[str, Any]
    plaintext: str


# ─── Indexa Capital ────────────────────────────────────────────────────────────


class IndexaPortfolioResponse(BaseModel):
    """Portfolio snapshot from Indexa Capital.

    Positions are flattened to {name, isin, amount, cost_amount, weight,
    asset_class, price, titles}. Totals come from raw.portfolio.
    """
    model_config = ConfigDict(extra="allow")

    positions: list[dict[str, Any]] = []
    total_value: float | None = None
    total_invested: float | None = None
    cash: float | None = None
    allocation: dict[str, Any] = {}
    raw: dict[str, Any] = {}


class IndexaPerformanceResponse(BaseModel):
    """Performance time series + KPIs from Indexa Capital.

    series is a sorted array of {date, value} pairs derived from
    raw.return.total_amounts. Returns (time_return, etc.) are fractional
    (0.527 == 52.7%).
    """
    model_config = ConfigDict(extra="allow")

    series: list[dict[str, Any]] = []
    time_return: float | None = None
    time_return_annual: float | None = None
    time_return_last_year: float | None = None
    time_return_last_month: float | None = None
    time_return_last_week: float | None = None
    pl: float | None = None
    investment: float | None = None
    total_amount: float | None = None
    volatility: float | None = None
    sharpe_ratio: float | None = None
    max_drawdown: float | None = None
    raw: dict[str, Any] = {}
