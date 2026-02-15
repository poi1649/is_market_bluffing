from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AnalysisRun, AnalysisRunResult
from app.schemas import AnalyzeRequest, AnalyzeResponse, RecoveryDistribution, RunSummary, RunsResponse, StockResult, TickerSearchResponse
from app.services.container import build_analysis_service


SESSION_HEADER = "x-anon-session-id"


router = APIRouter(prefix="/api/v1", tags=["analysis"])
analysis_service = build_analysis_service()


def _resolve_session_id(request: Request, response: Response) -> str:
    session_id = request.headers.get(SESSION_HEADER, "").strip()
    if not session_id:
        session_id = str(uuid4())
    response.headers[SESSION_HEADER] = session_id
    return session_id


def _stock_to_schema(item) -> StockResult:
    return StockResult(
        ticker=item.ticker,
        decline_pct=item.decline_pct,
        threshold_pct=item.threshold_pct,
        beta=item.beta,
        peak_date=item.peak_date,
        trough_date=item.trough_date,
        peak_price=item.peak_price,
        trough_price=item.trough_price,
        market_cap_musd=item.market_cap_musd,
        recovered=item.recovered,
        recovery_date=item.recovery_date,
        recovery_price=item.recovery_price,
        recovery_days=item.recovery_days,
        qualifying_events=item.qualifying_events,
        recovered_events=item.recovered_events,
    )


def _serialize_run(run: AnalysisRun, results: list[AnalysisRunResult], session_id: str) -> AnalyzeResponse:
    mapped_results = [
        StockResult(
            ticker=row.ticker,
            decline_pct=row.decline_pct,
            threshold_pct=row.threshold_pct,
            beta=row.beta,
            peak_date=row.peak_date,
            trough_date=row.trough_date,
            peak_price=row.peak_price,
            trough_price=row.trough_price,
            market_cap_musd=row.market_cap_musd,
            recovered=row.recovered,
            recovery_date=row.recovery_date,
            recovery_price=row.recovery_price,
            recovery_days=row.recovery_days,
            qualifying_events=row.qualifying_events,
            recovered_events=row.recovered_events,
        )
        for row in sorted(results, key=lambda item: item.decline_pct, reverse=True)
    ]

    recovered = [row for row in mapped_results if row.recovered]

    tickers = [value for value in run.tickers_csv.split(",") if value]
    return AnalyzeResponse(
        run_id=run.id,
        session_id=session_id,
        generated_at=run.created_at,
        params={
            "tickers": tickers,
            "lookback_months": run.lookback_months,
            "decline_threshold_pct": run.decline_threshold_pct,
            "min_market_cap_musd": run.min_market_cap_musd,
            "used_default_universe": run.used_default_universe,
        },
        universe_size=run.universe_size,
        evaluated_ticker_count=run.evaluated_ticker_count,
        declined_stock_count=run.declined_stock_count,
        recovered_stock_count=run.recovered_stock_count,
        stock_bluff_rate_pct=run.stock_bluff_rate_pct,
        declined_event_count=run.declined_event_count,
        recovered_event_count=run.recovered_event_count,
        event_bluff_rate_pct=run.event_bluff_rate_pct,
        recovery_days_distribution=RecoveryDistribution(
            p25=run.recovery_days_p25,
            median=run.recovery_days_median,
            p75=run.recovery_days_p75,
        ),
        declined_stocks=mapped_results,
        recovered_stocks=recovered,
    )


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(
    payload: AnalyzeRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    session_id = _resolve_session_id(request, response)

    used_default_universe = False
    universe_size = 0

    if payload.tickers:
        tickers = payload.tickers
        universe_size = len(tickers)
    else:
        universe = analysis_service.provider.get_default_universe()  # type: ignore[attr-defined]
        tickers = universe.tickers
        used_default_universe = True
        universe_size = len(tickers)

    summary = analysis_service.run(
        tickers=tickers,
        lookback_months=payload.lookback_months,
        decline_threshold_pct=payload.decline_threshold_pct,
        min_market_cap_musd=payload.min_market_cap_musd,
        used_default_universe=used_default_universe,
        universe_size=universe_size,
    )

    run_id = str(uuid4())
    run = AnalysisRun(
        id=run_id,
        session_id=session_id,
        created_at=datetime.utcnow(),
        tickers_csv=",".join(tickers),
        lookback_months=payload.lookback_months,
        decline_threshold_pct=payload.decline_threshold_pct,
        min_market_cap_musd=payload.min_market_cap_musd,
        used_default_universe=used_default_universe,
        universe_size=summary.universe_size,
        evaluated_ticker_count=summary.evaluated_ticker_count,
        declined_stock_count=summary.declined_stock_count,
        recovered_stock_count=summary.recovered_stock_count,
        stock_bluff_rate_pct=summary.stock_bluff_rate_pct,
        declined_event_count=summary.declined_event_count,
        recovered_event_count=summary.recovered_event_count,
        event_bluff_rate_pct=summary.event_bluff_rate_pct,
        recovery_days_p25=summary.recovery_days_distribution.get("p25"),
        recovery_days_median=summary.recovery_days_distribution.get("median"),
        recovery_days_p75=summary.recovery_days_distribution.get("p75"),
    )

    db.add(run)

    for item in summary.declined_stocks:
        db.add(
            AnalysisRunResult(
                run_id=run_id,
                ticker=item.ticker,
                peak_date=item.peak_date,
                trough_date=item.trough_date,
                decline_pct=item.decline_pct,
                threshold_pct=item.threshold_pct,
                beta=item.beta,
                peak_price=item.peak_price,
                trough_price=item.trough_price,
                market_cap_musd=item.market_cap_musd,
                recovered=item.recovered,
                recovery_date=item.recovery_date,
                recovery_price=item.recovery_price,
                recovery_days=item.recovery_days,
                qualifying_events=item.qualifying_events,
                recovered_events=item.recovered_events,
            )
        )

    db.commit()

    declined = [_stock_to_schema(item) for item in summary.declined_stocks]
    recovered = [_stock_to_schema(item) for item in summary.recovered_stocks]

    return AnalyzeResponse(
        run_id=run_id,
        session_id=session_id,
        generated_at=summary.generated_at,
        params=summary.params,
        universe_size=summary.universe_size,
        evaluated_ticker_count=summary.evaluated_ticker_count,
        declined_stock_count=summary.declined_stock_count,
        recovered_stock_count=summary.recovered_stock_count,
        stock_bluff_rate_pct=summary.stock_bluff_rate_pct,
        declined_event_count=summary.declined_event_count,
        recovered_event_count=summary.recovered_event_count,
        event_bluff_rate_pct=summary.event_bluff_rate_pct,
        recovery_days_distribution=RecoveryDistribution(**summary.recovery_days_distribution),
        declined_stocks=declined,
        recovered_stocks=recovered,
    )


@router.get("/runs", response_model=RunsResponse)
def list_runs(
    request: Request,
    response: Response,
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    session_id = _resolve_session_id(request, response)

    query = (
        select(AnalysisRun)
        .where(AnalysisRun.session_id == session_id)
        .order_by(desc(AnalysisRun.created_at))
        .limit(limit)
    )
    runs = db.scalars(query).all()

    items = [
        RunSummary(
            run_id=run.id,
            created_at=run.created_at,
            lookback_months=run.lookback_months,
            decline_threshold_pct=run.decline_threshold_pct,
            min_market_cap_musd=run.min_market_cap_musd,
            declined_stock_count=run.declined_stock_count,
            recovered_stock_count=run.recovered_stock_count,
            stock_bluff_rate_pct=run.stock_bluff_rate_pct,
        )
        for run in runs
    ]

    return RunsResponse(session_id=session_id, runs=items)


@router.get("/runs/{run_id}", response_model=AnalyzeResponse)
def get_run_detail(
    run_id: str,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    session_id = _resolve_session_id(request, response)

    run = db.scalar(
        select(AnalysisRun).where(
            AnalysisRun.id == run_id,
            AnalysisRun.session_id == session_id,
        )
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    results = db.scalars(select(AnalysisRunResult).where(AnalysisRunResult.run_id == run_id)).all()
    return _serialize_run(run, results, session_id)


@router.get("/tickers/search", response_model=TickerSearchResponse)
def search_tickers(q: str = Query(default="", min_length=0, max_length=32)):
    query = q.strip().upper()
    universe = analysis_service.provider.get_default_universe()  # type: ignore[attr-defined]

    tickers = universe.tickers
    if query:
        tickers = [ticker for ticker in tickers if query in ticker]

    return TickerSearchResponse(query=query, tickers=tickers[:100])
