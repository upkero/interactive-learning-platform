"""Threshold for excluding repeatedly reported widgets (story 1.4.10)."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ReportsSettings(BaseSettings):
    exclude_threshold: int = Field(
        default=3,
        gt=0,
        description="Number of distinct user reports after which a widget is excluded.",
    )

    model_config = SettingsConfigDict(env_prefix="REPORTS_", env_file=".env", extra="ignore")


@lru_cache(maxsize=1)
def get_reports_settings() -> ReportsSettings:
    return ReportsSettings()
