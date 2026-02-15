from contextlib import contextmanager

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.config import settings


engine = create_engine(settings.database_url, future=True, connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {})
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)
Base = declarative_base()


@contextmanager
def get_session() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_schema() -> None:
    with engine.begin() as conn:
        inspector = inspect(conn)
        if not inspector.has_table("analysis_run_results"):
            return

        columns = {column["name"] for column in inspector.get_columns("analysis_run_results")}
        if "recovery_price" not in columns:
            conn.execute(text("ALTER TABLE analysis_run_results ADD COLUMN recovery_price FLOAT"))
