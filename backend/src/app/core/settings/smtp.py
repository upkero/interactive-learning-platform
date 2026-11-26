from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SMTPSettings(BaseSettings):
    enabled: bool = Field(default=False, description="Send email when a document finishes.")
    host: str = Field(default="", description="SMTP server host; required when enabled.")
    port: int = Field(default=1025, gt=0, le=65535, description="SMTP server port.")
    username: str | None = Field(default=None, description="Optional SMTP login.")
    password: str | None = Field(default=None, description="Optional SMTP password.")
    from_email: str = Field(default="no-reply@example.com", description="Sender address.")
    use_tls: bool = Field(default=False, description="Use implicit TLS (port 465).")
    start_tls: bool = Field(default=False, description="Upgrade to TLS via STARTTLS (port 587).")
    timeout: float = Field(default=10.0, gt=0, description="SMTP connection and send timeout in seconds.")
    notification_ttl_seconds: int = Field(default=604800, gt=0, description="Idempotency key lifetime in seconds.")
    model_config = SettingsConfigDict(env_prefix="SMTP_", env_file=".env", extra="ignore")


def validate_smtp_config(environment: str, settings: SMTPSettings) -> None:
    host = settings.host.strip().rstrip(".").lower()
    if settings.enabled and (not host or (environment.lower() == "production" and host == "mailpit")):
        raise ValueError(
            "SMTP_ENABLED requires a configured external SMTP_HOST (Mailpit is not allowed in production)."
        )


@lru_cache(maxsize=1)
def get_smtp_settings() -> SMTPSettings:
    return SMTPSettings()
