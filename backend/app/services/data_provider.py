from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol

import pandas as pd


@dataclass
class UniverseData:
    source: str
    as_of: date | None
    tickers: list[str]


@dataclass
class TickerMeta:
    market_cap_musd: float | None
    beta: float


class MarketDataProvider(Protocol):
    def get_default_universe(self) -> UniverseData:
        ...

    def get_price_history(self, ticker: str, start_date: date, end_date: date) -> pd.DataFrame:
        ...

    def get_ticker_meta(self, ticker: str, beta_lookback_days: int) -> TickerMeta:
        ...
