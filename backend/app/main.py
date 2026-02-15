from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_cors_origins, settings
from app.db import Base, engine, ensure_schema
from app.routers import analysis, universe


Base.metadata.create_all(bind=engine)
ensure_schema()

app = FastAPI(title=settings.app_name)
cors_origins = get_cors_origins()

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["x-anon-session-id"],
)


@app.middleware("http")
async def enforce_strict_origin(request: Request, call_next):
    if not settings.strict_origin_check:
        return await call_next(request)

    if request.method == "OPTIONS":
        return await call_next(request)

    origin = request.headers.get("origin", "").strip()
    if origin not in cors_origins:
        return JSONResponse(status_code=403, content={"detail": "Forbidden origin"})

    return await call_next(request)

app.include_router(analysis.router)
app.include_router(universe.router)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
