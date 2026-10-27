from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    app_name: str = Field(default="grasp-backend", description="Имя приложения.")
    environment: str = Field(default="development", description="Окружение: development, test, production.")
    public_app_url: str = Field(default="http://localhost:3000", description="Публичный URL фронтенда.")

    # База данных PostgreSQL
    db_url: str = Field(
        default="postgresql+asyncpg://grasp:grasp@localhost:5432/grasp",
        description="Строка подключения к базе данных PostgreSQL через asyncpg.",
    )
    db_pool_size: int = Field(default=10, gt=0, description="Размер пула соединений SQLAlchemy.")
    db_max_overflow: int = Field(default=5, ge=0, description="Максимальное количество соединений сверх пула.")
    db_use_null_pool: bool = Field(
        default=False,
        description="Использовать ли NullPool (True для воркеров Celery, False для API).",
    )

    # CORS
    cors_allow_origins: list[str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000"],
        description="Список разрешенных Origin для CORS.",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_app_settings() -> AppSettings:
    return AppSettings()
