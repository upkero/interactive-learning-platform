from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class QuotaSettings(BaseSettings):
    default_monthly_limit: int = Field(
        default=20,
        ge=0,
        description="Месячный лимит бесплатных генераций для нового пользователя.",
    )

    model_config = SettingsConfigDict(
        env_prefix="QUOTA_",
        env_file=".env",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_quota_settings() -> QuotaSettings:
    return QuotaSettings()
