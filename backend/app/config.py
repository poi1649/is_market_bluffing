from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(BASE_DIR / ".env"), env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Is Market Bluffing"
    app_env: str = "development"
    frontend_origin: str = "http://localhost:3000"
    frontend_origins_csv: str = ""
    strict_origin_check: bool = True

    database_url: str = f"sqlite:///{(BASE_DIR / 'data.db').as_posix()}"

    price_cache_dir: str = (BASE_DIR / "app" / "cache" / "prices").as_posix()
    meta_cache_dir: str = (BASE_DIR / "app" / "cache" / "meta").as_posix()

    default_beta_lookback_days: int = 730
    default_universe_size: int = 300
    default_top_n_search: int = 50


settings = Settings()


def get_cors_origins() -> list[str]:
    origins: list[str] = []

    if settings.frontend_origin.strip():
        origins.append(settings.frontend_origin.strip())

    for value in settings.frontend_origins_csv.split(","):
        item = value.strip()
        if item:
            origins.append(item)

    if settings.app_env.lower() != "production":
        if "http://localhost:3000" not in origins:
            origins.append("http://localhost:3000")
        if "http://127.0.0.1:3000" not in origins:
            origins.append("http://127.0.0.1:3000")

    deduped: list[str] = []
    seen: set[str] = set()
    for origin in origins:
        if origin in seen:
            continue
        seen.add(origin)
        deduped.append(origin)
    return deduped
