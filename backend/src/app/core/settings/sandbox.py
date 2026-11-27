from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SandboxSettings(BaseSettings):
    url: str = Field(default="http://sandbox:3001", description="Sandbox internal service URL.")
    timeout_seconds: float = Field(default=35.0, gt=0)

    model_config = SettingsConfigDict(env_prefix="SANDBOX_", env_file=".env", extra="ignore")


@lru_cache(maxsize=1)
def get_sandbox_settings() -> SandboxSettings:
    return SandboxSettings()
