from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class StorageSettings(BaseSettings):
    endpoint_url: str = Field(default="http://localhost:9000", description="Внутренний адрес MinIO для бэкенда.")
    public_endpoint_url: str = Field(
        default="http://localhost:9000",
        description="Публичный адрес MinIO для подписи presigned-ссылок в браузере.",
    )
    access_key_id: str = Field(default="minioadmin", description="Логин администратора MinIO.")
    secret_access_key: SecretStr = Field(
        default=SecretStr("minioadmin"),
        description="Секретный пароль MinIO.",
    )
    region_name: str = Field(default="us-east-1", description="Регион S3.")
    bucket_documents: str = Field(default="documents", description="Бакет для исходных PDF/DOCX файлов.")
    bucket_images: str = Field(default="images", description="Бакет для извлеченных картинок.")
    presign_ttl_seconds: int = Field(default=3600, gt=0, description="Срок жизни временной ссылки на картинку.")

    model_config = SettingsConfigDict(
        env_prefix="S3_",
        env_file=".env",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_storage_settings() -> StorageSettings:
    return StorageSettings()
