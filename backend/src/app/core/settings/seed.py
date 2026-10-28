from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SeedSettings(BaseSettings):
    """Settings of the seed CLI; required so no default password leaks."""

    seed_password: str = Field(description="Password assigned to the seeded demo users (SEED_PASSWORD).")

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_seed_settings() -> SeedSettings:
    return SeedSettings()
