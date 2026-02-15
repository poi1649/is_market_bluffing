from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_cors_origins, settings
from app.db import Base, engine, ensure_schema
from app.routers import analysis, universe


Base.metadata.create_all(bind=engine)
ensure_schema()

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["x-anon-session-id"],
)

app.include_router(analysis.router)
app.include_router(universe.router)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
