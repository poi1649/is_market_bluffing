from fastapi import APIRouter

from app.schemas import UniverseResponse
from app.services.container import build_analysis_service


router = APIRouter(prefix="/api/v1", tags=["universe"])
analysis_service = build_analysis_service()


@router.get("/universe/default", response_model=UniverseResponse)
def get_default_universe():
    universe = analysis_service.provider.get_default_universe()  # type: ignore[attr-defined]
    return UniverseResponse(
        source=universe.source,
        as_of=universe.as_of,
        ticker_count=len(universe.tickers),
        tickers=universe.tickers,
    )
