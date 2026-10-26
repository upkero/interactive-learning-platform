from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthSettings(BaseSettings):
    jwt_secret: SecretStr = Field(
        ...,
        min_length=32,
        description="Секретный ключ для подписи токенов JWT (минимум 32 символа).",
    )
    session_ttl_seconds: int = Field(
        default=604_800,  # 7 дней
        gt=0,
        description="Срок жизни сессионной cookie в секундах (7 дней).",
    )
    cookie_secure: bool = Field(
        default=False,
        description="Устанавливать ли флаг Secure для cookie (True для production по HTTPS).",
    )
    session_cookie_name: str = Field(
        default="grasp_session",
        description="Имя httpOnly cookie для хранения сессии.",
    )

    model_config = SettingsConfigDict(
        env_prefix="AUTH_",
        env_file=".env",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_auth_settings() -> AuthSettings:
    return AuthSettings()
