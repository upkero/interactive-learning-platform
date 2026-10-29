from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthSettings(BaseSettings):
    jwt_secret: SecretStr = Field(
        ...,
        min_length=32,
        description="Secret key used to sign JWT tokens (at least 32 characters).",
    )
    session_ttl_seconds: int = Field(
        default=604_800,  # 7 days
        gt=0,
        description="Session cookie lifetime in seconds (7 days).",
    )
    cookie_secure: bool = Field(
        default=False,
        description="Set the Secure flag on the cookie (True for production over HTTPS).",
    )
    session_cookie_name: str = Field(
        default="grasp_session",
        description="Name of the httpOnly session cookie.",
    )

    model_config = SettingsConfigDict(
        env_prefix="AUTH_",
        env_file=".env",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_auth_settings() -> AuthSettings:
    return AuthSettings()
