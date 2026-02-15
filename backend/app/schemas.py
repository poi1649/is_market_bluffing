from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class AnalyzeRequest(BaseModel):
    tickers: list[str] = Field(default_factory=list)
    lookback_months: int = Field(default=6, ge=1, le=60)
    decline_threshold_pct: float = Field(default=20.0, gt=0.0, le=100.0)
    min_market_cap_musd: float = Field(default=0.0, ge=0.0)

    @field_validator("tickers")
    @classmethod
    def normalize_tickers(cls, values: list[str]) -> list[str]:
        normalized = {
            ticker.strip().upper().replace(".", "-")
            for ticker in values
            if ticker and ticker.strip()
        }
        return sorted(normalized)


class RecoveryDistribution(BaseModel):
    p25: float | None = None
    median: float | None = None
    p75: float | None = None


class StockResult(BaseModel):
    ticker: str
    decline_pct: float
    threshold_pct: float
    beta: float

    peak_date: date
    trough_date: date

    peak_price: float
    trough_price: float

    market_cap_musd: float | None = None

    recovered: bool
    recovery_date: date | None = None
    recovery_price: float | None = None
    recovery_days: int | None = None

    qualifying_events: int = 0
    recovered_events: int = 0


class AnalyzeResponse(BaseModel):
    run_id: str
    session_id: str
    generated_at: datetime

    params: dict[str, Any]

    universe_size: int
    evaluated_ticker_count: int

    declined_stock_count: int
    recovered_stock_count: int
    stock_bluff_rate_pct: float

    declined_event_count: int
    recovered_event_count: int
    event_bluff_rate_pct: float

    recovery_days_distribution: RecoveryDistribution

    declined_stocks: list[StockResult]
    recovered_stocks: list[StockResult]


class RunSummary(BaseModel):
    run_id: str
    created_at: datetime

    lookback_months: int
    decline_threshold_pct: float
    min_market_cap_musd: float

    declined_stock_count: int
    recovered_stock_count: int
    stock_bluff_rate_pct: float


class RunsResponse(BaseModel):
    session_id: str
    runs: list[RunSummary]


class UniverseResponse(BaseModel):
    source: str
    as_of: date | None = None
    ticker_count: int
    tickers: list[str]


class TickerSearchResponse(BaseModel):
    query: str
    tickers: list[str]
