from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime

import numpy as np
import pandas as pd
from dateutil.relativedelta import relativedelta

from app.services.data_provider import MarketDataProvider

logger = logging.getLogger(__name__)


@dataclass
class EventData:
    peak_date: date
    trough_date: date
    decline_pct: float
    peak_price: float
    trough_price: float
    recovered: bool
    recovery_date: date | None
    recovery_price: float | None
    recovery_days: int | None


@dataclass
class StockAnalysis:
    ticker: str
    decline_pct: float
    threshold_pct: float
    beta: float

    peak_date: date
    trough_date: date

    peak_price: float
    trough_price: float

    market_cap_musd: float | None

    recovered: bool
    recovery_date: date | None
    recovery_price: float | None
    recovery_days: int | None

    qualifying_events: int
    recovered_events: int


@dataclass
class AnalysisSummary:
    generated_at: datetime
    params: dict

    universe_size: int
    evaluated_ticker_count: int

    declined_stock_count: int
    recovered_stock_count: int
    stock_bluff_rate_pct: float

    declined_event_count: int
    recovered_event_count: int
    event_bluff_rate_pct: float

    recovery_days_distribution: dict[str, float | None]
    failed_ticker_count: int
    failed_tickers: list[str]

    declined_stocks: list[StockAnalysis]
    recovered_stocks: list[StockAnalysis]


class BluffAnalysisService:
    def __init__(self, provider: MarketDataProvider, beta_lookback_days: int = 730) -> None:
        self.provider = provider
        self.beta_lookback_days = beta_lookback_days

    def run(
        self,
        tickers: list[str],
        lookback_months: int,
        decline_threshold_pct: float,
        min_market_cap_musd: float,
        used_default_universe: bool,
        universe_size: int,
    ) -> AnalysisSummary:
        end_date = date.today()
        start_date = end_date - relativedelta(months=lookback_months)

        declined_stocks: list[StockAnalysis] = []
        declined_event_count = 0
        recovered_event_count = 0
        failed_tickers: list[str] = []

        max_workers = min(16, max(1, (os.cpu_count() or 4) * 4), max(1, len(tickers)))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {
                executor.submit(
                    self._analyze_ticker,
                    ticker=ticker,
                    start_date=start_date,
                    end_date=end_date,
                    decline_threshold_pct=decline_threshold_pct,
                    min_market_cap_musd=min_market_cap_musd,
                ): ticker
                for ticker in tickers
            }
            for future in as_completed(future_map):
                ticker = future_map[future]
                try:
                    outcome = future.result()
                except Exception:
                    logger.exception("Ticker %s failed during analysis and was excluded from result", ticker)
                    failed_tickers.append(ticker)
                    continue

                if outcome is None:
                    continue

                if isinstance(outcome, str):
                    failed_tickers.append(outcome)
                    continue

                stock, ticker_declined_event_count, ticker_recovered_event_count = outcome
                if stock is not None:
                    declined_stocks.append(stock)
                declined_event_count += ticker_declined_event_count
                recovered_event_count += ticker_recovered_event_count

        declined_stocks.sort(key=lambda item: item.decline_pct, reverse=True)
        recovered_stocks = [item for item in declined_stocks if item.recovered]

        declined_stock_count = len(declined_stocks)
        recovered_stock_count = len(recovered_stocks)

        stock_bluff_rate = _safe_ratio(recovered_stock_count, declined_stock_count)
        event_bluff_rate = _safe_ratio(recovered_event_count, declined_event_count)

        recovery_days_values = [float(item.recovery_days) for item in recovered_stocks if item.recovery_days is not None]
        distribution = _distribution(recovery_days_values)

        return AnalysisSummary(
            generated_at=datetime.utcnow(),
            params={
                "tickers": tickers,
                "lookback_months": lookback_months,
                "decline_threshold_pct": decline_threshold_pct,
                "min_market_cap_musd": min_market_cap_musd,
                "used_default_universe": used_default_universe,
            },
            universe_size=universe_size,
            evaluated_ticker_count=len(tickers),
            declined_stock_count=declined_stock_count,
            recovered_stock_count=recovered_stock_count,
            stock_bluff_rate_pct=round(stock_bluff_rate * 100.0, 4),
            declined_event_count=declined_event_count,
            recovered_event_count=recovered_event_count,
            event_bluff_rate_pct=round(event_bluff_rate * 100.0, 4),
            recovery_days_distribution=distribution,
            failed_ticker_count=len(failed_tickers),
            failed_tickers=sorted(set(failed_tickers)),
            declined_stocks=declined_stocks,
            recovered_stocks=recovered_stocks,
        )

    def _analyze_ticker(
        self,
        ticker: str,
        start_date: date,
        end_date: date,
        decline_threshold_pct: float,
        min_market_cap_musd: float,
    ) -> tuple[StockAnalysis | None, int, int] | str | None:
        try:
            prices = self.provider.get_price_history(ticker, start_date, end_date)
            if prices.empty or len(prices) < 2:
                logger.warning("Ticker %s skipped: no usable price history in lookback window", ticker)
                return ticker

            meta = self.provider.get_ticker_meta(ticker, self.beta_lookback_days)
            if meta.market_cap_musd is not None and meta.market_cap_musd < min_market_cap_musd:
                return None

            beta = float(meta.beta)
            threshold = decline_threshold_pct * max(1.0, beta)

            events = _find_qualifying_events(prices, threshold)
            if not events:
                return None

            recovered_events = [event for event in events if event.recovered]
            recovered = bool(recovered_events)

            # Keep representative event for display, but stock-level recovery is true if any qualifying event recovered.
            if recovered:
                representative = max(recovered_events, key=lambda event: event.decline_pct)
            else:
                representative = max(events, key=lambda event: event.decline_pct)

            recovery_date = representative.recovery_date if representative.recovered else None
            recovery_price = representative.recovery_price if representative.recovered else None
            recovery_days = representative.recovery_days if representative.recovered else None

            stock = StockAnalysis(
                ticker=ticker,
                decline_pct=round(representative.decline_pct, 4),
                threshold_pct=round(threshold, 4),
                beta=round(beta, 4),
                peak_date=representative.peak_date,
                trough_date=representative.trough_date,
                peak_price=round(representative.peak_price, 4),
                trough_price=round(representative.trough_price, 4),
                market_cap_musd=round(meta.market_cap_musd, 3) if meta.market_cap_musd is not None else None,
                recovered=recovered,
                recovery_date=recovery_date,
                recovery_price=round(recovery_price, 4) if recovery_price is not None else None,
                recovery_days=recovery_days,
                qualifying_events=len(events),
                recovered_events=len(recovered_events),
            )
            return stock, len(events), len(recovered_events)
        except Exception:
            logger.exception("Ticker %s failed during analysis and was excluded from result", ticker)
            return ticker


def _safe_ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def _distribution(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"p25": None, "median": None, "p75": None}

    arr = np.array(values)
    return {
        "p25": round(float(np.percentile(arr, 25)), 4),
        "median": round(float(np.percentile(arr, 50)), 4),
        "p75": round(float(np.percentile(arr, 75)), 4),
    }


def _find_qualifying_events(prices: pd.DataFrame, threshold_pct: float) -> list[EventData]:
    if prices.empty:
        return []

    frame = prices.sort_index().copy()
    frame = frame[["High", "Low"]].dropna()
    if frame.empty or len(frame) < 2:
        return []

    events: list[EventData] = []

    rows = list(frame.iterrows())
    first_date = rows[0][0].date()
    peak_price = float(rows[0][1]["High"])
    peak_date = first_date

    state = "tracking_peak"
    event_peak_price = peak_price
    event_peak_date = peak_date
    trigger_price = peak_price
    trigger_date = peak_date

    for idx in range(1, len(rows)):
        timestamp, row = rows[idx]
        current_date = timestamp.date()
        high = float(row["High"])
        low = float(row["Low"])

        if state == "tracking_peak":
            if high > peak_price:
                peak_price = high
                peak_date = current_date

            if current_date > peak_date:
                decline = (peak_price - low) / peak_price * 100.0
                if decline >= threshold_pct:
                    state = "in_drawdown"
                    event_peak_price = peak_price
                    event_peak_date = peak_date
                    trigger_price = low
                    trigger_date = current_date

        else:
            if high >= event_peak_price and current_date > trigger_date:
                decline = (event_peak_price - trigger_price) / event_peak_price * 100.0
                recovery_days = (current_date - trigger_date).days
                events.append(
                    EventData(
                        peak_date=event_peak_date,
                        trough_date=trigger_date,
                        decline_pct=decline,
                        peak_price=event_peak_price,
                        trough_price=trigger_price,
                        recovered=True,
                        recovery_date=current_date,
                        recovery_price=high,
                        recovery_days=recovery_days,
                    )
                )

                state = "tracking_peak"
                peak_price = high
                peak_date = current_date

    if state == "in_drawdown":
        decline = (event_peak_price - trigger_price) / event_peak_price * 100.0
        events.append(
            EventData(
                peak_date=event_peak_date,
                trough_date=trigger_date,
                decline_pct=decline,
                peak_price=event_peak_price,
                trough_price=trigger_price,
                recovered=False,
                recovery_date=None,
                recovery_price=None,
                recovery_days=None,
            )
        )

    return events
