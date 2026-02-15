from datetime import datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    tickers_csv: Mapped[str] = mapped_column(Text, default="", nullable=False)
    lookback_months: Mapped[int] = mapped_column(Integer, nullable=False)
    decline_threshold_pct: Mapped[float] = mapped_column(Float, nullable=False)
    min_market_cap_musd: Mapped[float] = mapped_column(Float, nullable=False)
    used_default_universe: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    universe_size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    evaluated_ticker_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    declined_stock_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    recovered_stock_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    stock_bluff_rate_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    declined_event_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    recovered_event_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    event_bluff_rate_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    recovery_days_p25: Mapped[float | None] = mapped_column(Float, nullable=True)
    recovery_days_median: Mapped[float | None] = mapped_column(Float, nullable=True)
    recovery_days_p75: Mapped[float | None] = mapped_column(Float, nullable=True)

    results: Mapped[list["AnalysisRunResult"]] = relationship(back_populates="run", cascade="all, delete-orphan")


class AnalysisRunResult(Base):
    __tablename__ = "analysis_run_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False, index=True)

    ticker: Mapped[str] = mapped_column(String(16), index=True, nullable=False)

    peak_date: Mapped[Date] = mapped_column(Date, nullable=False)
    trough_date: Mapped[Date] = mapped_column(Date, nullable=False)
    decline_pct: Mapped[float] = mapped_column(Float, nullable=False)
    threshold_pct: Mapped[float] = mapped_column(Float, nullable=False)
    beta: Mapped[float] = mapped_column(Float, nullable=False)

    peak_price: Mapped[float] = mapped_column(Float, nullable=False)
    trough_price: Mapped[float] = mapped_column(Float, nullable=False)

    market_cap_musd: Mapped[float | None] = mapped_column(Float, nullable=True)

    recovered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    recovery_date: Mapped[Date | None] = mapped_column(Date, nullable=True)
    recovery_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    recovery_days: Mapped[int | None] = mapped_column(Integer, nullable=True)

    qualifying_events: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    recovered_events: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    run: Mapped[AnalysisRun] = relationship(back_populates="results")
