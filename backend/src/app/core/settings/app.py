from functools import lru_cache

from pydantic import Field, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    db_url: PostgresDsn | None = Field(
        default=None,
        description="PostgreSQL async connection URL (postgresql+asyncpg://...).",
    )
    cors_allow_origins: list[str] = Field(
        default=["*"],
        description="Allowed CORS origins. Restrict in production.",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_app_settings() -> AppSettings:
    return AppSettings()
