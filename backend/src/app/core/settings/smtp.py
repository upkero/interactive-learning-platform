from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SMTPSettings(BaseSettings):
    host: str = Field(default="mailpit", description="SMTP server host.")
    port: int = Field(default=1025, gt=0, le=65535)
    username: str | None = None
    password: str | None = None
    from_email: str = "no-reply@grasp.local"
    use_tls: bool = False
    model_config = SettingsConfigDict(env_prefix="SMTP_", env_file=".env", extra="ignore")


@lru_cache(maxsize=1)
def get_smtp_settings() -> SMTPSettings:
    return SMTPSettings()
