from app.config import settings
from app.services.analysis import BluffAnalysisService
from app.services.yfinance_provider import YFinanceMarketDataProvider


def build_analysis_service() -> BluffAnalysisService:
    provider = YFinanceMarketDataProvider()
    return BluffAnalysisService(provider=provider, beta_lookback_days=settings.default_beta_lookback_days)
