from __future__ import annotations

import json
import io
import logging
import os
from contextlib import redirect_stderr, redirect_stdout
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

RUNTIME_CACHE_HOME = Path("/tmp/is_market_bluffing/.cache")
try:
    RUNTIME_CACHE_HOME.mkdir(parents=True, exist_ok=True)
except Exception:
    # Best effort only; yfinance may still use its own fallback.
    pass
os.environ.setdefault("XDG_CACHE_HOME", RUNTIME_CACHE_HOME.as_posix())

import yfinance as yf

from app.config import settings
from app.services.data_provider import MarketDataProvider, TickerMeta, UniverseData

logger = logging.getLogger(__name__)


FALLBACK_SP500_TICKERS = [
    "AAPL", "MSFT", "AMZN", "NVDA", "GOOGL", "GOOG", "META", "BRK-B", "JPM", "V", "UNH", "XOM", "LLY", "MA", "AVGO", "PG", "HD", "MRK", "COST", "KO",
    "PEP", "ABBV", "ADBE", "BAC", "CRM", "WMT", "NFLX", "MCD", "CSCO", "TMO", "PFE", "ABT", "AMD", "ACN", "CMCSA", "DHR", "LIN", "TXN", "WFC", "DIS",
    "AMGN", "VZ", "INTU", "QCOM", "INTC", "UPS", "PM", "RTX", "LOW", "HON", "NEE", "UNP", "SBUX", "ORCL", "CAT", "IBM", "GS", "SPGI", "MS", "CVX",
    "AMAT", "BLK", "DE", "GILD", "MDT", "LMT", "C", "T", "BA", "AXP", "BKNG", "TJX", "CI", "SYK", "ADP", "ZTS", "PLD", "ISRG", "MMC", "MO",
    "SCHW", "GE", "CB", "SO", "ADI", "PNC", "ELV", "DUK", "TMUS", "MU", "AON", "VRTX", "REGN", "BSX", "CL", "APD", "ITW", "SHW", "SNPS", "EOG",
]

LEGACY_TICKER_MAP = {
    # AmerisourceBergen renamed to Cencora
    "ABC": "COR",
}


class YFinanceMarketDataProvider(MarketDataProvider):
    def __init__(self) -> None:
        self._configure_yfinance_cache()
        self.price_cache_dir = self._resolve_writable_dir(Path(settings.price_cache_dir), "prices")
        self.meta_cache_dir = self._resolve_writable_dir(Path(settings.meta_cache_dir), "meta")
        self.data_dir = Path(__file__).resolve().parent.parent / "data"
        self.runtime_data_dir = self._resolve_writable_dir(Path("/tmp/is_market_bluffing/data"), "data")
        self.default_universe_size = int(settings.default_universe_size)

        # `data_dir` is packaged as read-only in serverless; do not attempt to create it.

        self.sp500_snapshot_path = self.data_dir / "sp500_snapshot_feb2026.csv"
        self.sp500_live_cache_path = self.runtime_data_dir / "sp500_live_cache.csv"
        self.default_universe_seed_path = self.data_dir / "default_universe_300.csv"

    def _configure_yfinance_cache(self) -> None:
        cache_root = Path("/tmp/is_market_bluffing/yfinance-cache")
        cache_root.mkdir(parents=True, exist_ok=True)
        cache_path = cache_root.as_posix()

        try:
            yf.set_tz_cache_location(cache_path)
        except Exception:
            logger.exception("Failed to set yfinance tz cache location: %s", cache_path)

        try:
            from yfinance import cache as yf_cache  # type: ignore

            set_cache_location = getattr(yf_cache, "set_cache_location", None)
            if callable(set_cache_location):
                set_cache_location(cache_path)
        except Exception:
            logger.exception("Failed to set yfinance general cache location: %s", cache_path)

    def _resolve_writable_dir(self, preferred: Path, fallback_leaf: str) -> Path:
        try:
            preferred.mkdir(parents=True, exist_ok=True)
            probe = preferred / ".write_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return preferred
        except Exception:
            fallback = Path("/tmp/is_market_bluffing") / fallback_leaf
            fallback.mkdir(parents=True, exist_ok=True)
            return fallback

    def get_default_universe(self) -> UniverseData:
        live = self._load_live_sp500_if_available()
        if live is not None:
            return self._resize_default_universe(live)

        snapshot = self._load_snapshot_sp500()
        if snapshot is not None:
            return self._resize_default_universe(snapshot)

        seed = self._load_default_seed_tickers()
        return self._resize_default_universe(UniverseData(source="fallback-static", as_of=None, tickers=seed))

    def get_price_history(self, ticker: str, start_date: date, end_date: date) -> pd.DataFrame:
        normalized = self._normalize_ticker(ticker)
        cached = self._read_price_cache(normalized)
        if not cached.empty and self._cache_covers(cached, start_date, end_date):
            return self._slice_prices(cached, start_date, end_date)

        fetched = self._fetch_price_history(normalized)
        if fetched.empty:
            return pd.DataFrame(columns=["High", "Low", "Close"])

        self._write_price_cache(normalized, fetched)
        return self._slice_prices(fetched, start_date, end_date)

    def get_ticker_meta(self, ticker: str, beta_lookback_days: int) -> TickerMeta:
        normalized = self._normalize_ticker(ticker)
        today_str = date.today().isoformat()
        cached = self._read_meta_cache(normalized)

        market_cap_musd = None
        beta_value = None

        if cached.get("as_of") == today_str:
            market_cap_musd = cached.get("market_cap_musd")

        if (
            cached.get("beta_as_of") == today_str
            and cached.get("beta_lookback_days") == beta_lookback_days
            and cached.get("beta_value") is not None
        ):
            beta_value = float(cached["beta_value"])

        if market_cap_musd is None:
            market_cap_musd = self._fetch_market_cap_musd(normalized)

        if beta_value is None:
            beta_value = self._compute_beta(normalized, beta_lookback_days)

        payload = {
            "as_of": today_str,
            "market_cap_musd": market_cap_musd,
            "beta_as_of": today_str,
            "beta_lookback_days": beta_lookback_days,
            "beta_value": beta_value,
        }
        self._write_meta_cache(normalized, payload)

        return TickerMeta(market_cap_musd=market_cap_musd, beta=beta_value)

    def _normalize_ticker(self, ticker: str) -> str:
        normalized = ticker.strip().upper().replace(".", "-")
        return LEGACY_TICKER_MAP.get(normalized, normalized)

    def _dedupe_keep_order(self, tickers: list[str]) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for raw in tickers:
            ticker = self._normalize_ticker(str(raw))
            if not ticker or ticker in seen:
                continue
            seen.add(ticker)
            ordered.append(ticker)
        return ordered

    def _safe_file_name(self, ticker: str) -> str:
        return ticker.replace("/", "_")

    def _price_cache_path(self, ticker: str) -> Path:
        return self.price_cache_dir / f"{self._safe_file_name(ticker)}.csv"

    def _meta_cache_path(self, ticker: str) -> Path:
        return self.meta_cache_dir / f"{self._safe_file_name(ticker)}.json"

    def _load_live_sp500_if_available(self) -> UniverseData | None:
        if self.sp500_live_cache_path.exists():
            try:
                frame = pd.read_csv(self.sp500_live_cache_path)
                if "ticker" in frame.columns and not frame.empty:
                    as_of = None
                    if "as_of" in frame.columns and frame["as_of"].iloc[0]:
                        as_of = datetime.strptime(str(frame["as_of"].iloc[0]), "%Y-%m-%d").date()

                    if as_of == date.today():
                        return UniverseData(
                            source="wikipedia-live-cache",
                            as_of=as_of,
                            tickers=sorted(set(frame["ticker"].astype(str).str.upper().str.replace(".", "-", regex=False))),
                        )
            except Exception:
                pass

        try:
            frame = pd.read_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")[0]
            if "Symbol" not in frame.columns:
                return None

            tickers = sorted(set(frame["Symbol"].astype(str).str.upper().str.replace(".", "-", regex=False)))
            save = pd.DataFrame({"ticker": tickers, "as_of": [date.today().isoformat()] * len(tickers)})
            save.to_csv(self.sp500_live_cache_path, index=False)
            return UniverseData(source="wikipedia-live", as_of=date.today(), tickers=tickers)
        except Exception:
            return None

    def _load_snapshot_sp500(self) -> UniverseData | None:
        if not self.sp500_snapshot_path.exists():
            return None

        frame = pd.read_csv(self.sp500_snapshot_path)
        if "ticker" not in frame.columns or frame.empty:
            return None

        as_of = None
        if "as_of" in frame.columns:
            as_of_value = str(frame["as_of"].iloc[0])
            try:
                as_of = datetime.strptime(as_of_value, "%Y-%m-%d").date()
            except Exception:
                as_of = None

        tickers = sorted(set(frame["ticker"].astype(str).str.upper().str.replace(".", "-", regex=False)))
        return UniverseData(source="snapshot-feb2026", as_of=as_of, tickers=tickers)

    def _load_default_seed_tickers(self) -> list[str]:
        if self.default_universe_seed_path.exists():
            try:
                frame = pd.read_csv(self.default_universe_seed_path)
                if "ticker" in frame.columns and not frame.empty:
                    tickers = frame["ticker"].astype(str).tolist()
                    deduped = self._dedupe_keep_order(tickers)
                    if deduped:
                        return deduped
            except Exception:
                pass

        return self._dedupe_keep_order(FALLBACK_SP500_TICKERS)

    def _resize_default_universe(self, universe: UniverseData) -> UniverseData:
        tickers = self._dedupe_keep_order(list(universe.tickers))
        target_size = max(1, self.default_universe_size)

        if len(tickers) < target_size:
            seed = self._load_default_seed_tickers()
            for ticker in seed:
                if ticker not in tickers:
                    tickers.append(ticker)
                if len(tickers) >= target_size:
                    break

        if len(tickers) > target_size:
            tickers = tickers[:target_size]

        source = universe.source
        if source and not source.endswith(f"-top{target_size}"):
            source = f"{source}-top{target_size}"

        return UniverseData(source=source, as_of=universe.as_of, tickers=tickers)

    def _read_price_cache(self, ticker: str) -> pd.DataFrame:
        path = self._price_cache_path(ticker)
        if not path.exists():
            return pd.DataFrame(columns=["High", "Low", "Close"])

        try:
            frame = pd.read_csv(path, parse_dates=["Date"])  # type: ignore[arg-type]
            if frame.empty:
                return pd.DataFrame(columns=["High", "Low", "Close"])
            frame = frame.set_index("Date").sort_index()
            return frame[["High", "Low", "Close"]]
        except Exception:
            return pd.DataFrame(columns=["High", "Low", "Close"])

    def _write_price_cache(self, ticker: str, frame: pd.DataFrame) -> None:
        save = frame.copy()
        save = save.reset_index().rename(columns={"index": "Date"})
        if "Date" not in save.columns:
            save.rename(columns={save.columns[0]: "Date"}, inplace=True)
        save.to_csv(self._price_cache_path(ticker), index=False)

    def _cache_covers(self, frame: pd.DataFrame, start_date: date, end_date: date) -> bool:
        if frame.empty:
            return False
        first = frame.index.min().date()
        last = frame.index.max().date()
        return first <= start_date and last >= end_date - timedelta(days=2)

    def _slice_prices(self, frame: pd.DataFrame, start_date: date, end_date: date) -> pd.DataFrame:
        sliced = frame.loc[(frame.index.date >= start_date) & (frame.index.date <= end_date)].copy()
        if sliced.empty:
            return pd.DataFrame(columns=["High", "Low", "Close"])
        return sliced[["High", "Low", "Close"]]

    def _fetch_price_history(self, ticker: str) -> pd.DataFrame:
        try:
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                frame = yf.download(
                    ticker,
                    period="10y",
                    interval="1d",
                    auto_adjust=False,
                    progress=False,
                    group_by="ticker",
                    actions=False,
                    threads=False,
                )
        except Exception:
            logger.exception("Price download failed for ticker=%s", ticker)
            return pd.DataFrame(columns=["High", "Low", "Close"])

        if frame is None or frame.empty:
            logger.warning("Price download returned empty frame for ticker=%s", ticker)
            return pd.DataFrame(columns=["High", "Low", "Close"])

        if isinstance(frame.columns, pd.MultiIndex):
            frame.columns = frame.columns.get_level_values(-1)

        for col in ["High", "Low", "Close"]:
            if col not in frame.columns:
                return pd.DataFrame(columns=["High", "Low", "Close"])

        out = frame[["High", "Low", "Close"]].dropna().sort_index()
        if out.empty:
            logger.warning("Price frame has no usable OHLC rows for ticker=%s", ticker)
        return out

    def _read_meta_cache(self, ticker: str) -> dict:
        path = self._meta_cache_path(ticker)
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _write_meta_cache(self, ticker: str, payload: dict) -> None:
        path = self._meta_cache_path(ticker)
        path.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")

    def _fetch_market_cap_musd(self, ticker: str) -> float | None:
        try:
            obj = yf.Ticker(ticker)
            fast = getattr(obj, "fast_info", {}) or {}
            market_cap = fast.get("market_cap")
            if market_cap is None:
                info = getattr(obj, "info", {}) or {}
                market_cap = info.get("marketCap")
            if market_cap is None:
                logger.warning("Market cap missing for ticker=%s", ticker)
                return None
            return float(market_cap) / 1_000_000.0
        except Exception:
            logger.exception("Market cap fetch failed for ticker=%s", ticker)
            return None

    def _compute_beta(self, ticker: str, beta_lookback_days: int) -> float:
        end_date = date.today()
        start_date = end_date - timedelta(days=beta_lookback_days)

        stock = self.get_price_history(ticker, start_date, end_date)
        market = self.get_price_history("^GSPC", start_date, end_date)

        if stock.empty or market.empty:
            return 1.0

        joined = pd.DataFrame(
            {
                "stock": stock["Close"],
                "market": market["Close"],
            }
        ).dropna()

        if len(joined) < 60:
            return 1.0

        returns = joined.pct_change().dropna()
        if returns.empty:
            return 1.0

        market_var = float(np.var(returns["market"].to_numpy(), ddof=1))
        if market_var <= 1e-12:
            return 1.0

        cov = float(np.cov(returns["stock"].to_numpy(), returns["market"].to_numpy(), ddof=1)[0, 1])
        beta = cov / market_var

        if not np.isfinite(beta):
            return 1.0

        return float(beta)
