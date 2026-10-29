from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    app_name: str = Field(default="grasp-backend", description="Application name.")
    environment: str = Field(default="development", description="Environment: development, test, production.")
    public_app_url: str = Field(default="http://localhost:3000", description="Public URL of the frontend.")

    # PostgreSQL and SQLAlchemy connection pool settings
    db_url: str = Field(
        default="postgresql+asyncpg://grasp:grasp_dev_password@localhost:5432/grasp",
        description="PostgreSQL connection URL over asyncpg.",
    )
    db_pool_size: int = Field(default=10, gt=0, description="Size of the SQLAlchemy connection pool.")
    db_max_overflow: int = Field(default=5, ge=0, description="Maximum extra connections above the pool.")
    db_use_null_pool: bool = Field(
        default=False,
        description="Use NullPool (True for Celery workers, False for the API).",
    )

    # The web client calls the API through the Next.js proxy, so browser
    # CORS is not exercised by default; set CORS_ALLOW_ORIGINS only when a
    # client talks to the backend cross-origin directly.
    cors_allow_origins: list[str] = Field(
        default=[],
        description="Allowed CORS origins (empty by default; the frontend goes through the Next.js proxy).",
    )

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache(maxsize=1)
def get_app_settings() -> AppSettings:
    return AppSettings()
