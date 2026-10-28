from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class StorageSettings(BaseSettings):
    endpoint_url: str = Field(
        default="http://localhost:9000", description="Internal MinIO address used by the backend."
    )
    public_endpoint_url: str = Field(
        default="http://localhost:9000",
        description="Public MinIO address used to presign image links in the browser.",
    )
    access_key_id: str = Field(default="minioadmin", description="MinIO administrator login.")
    secret_access_key: SecretStr = Field(
        default=SecretStr("minioadmin"),
        description="MinIO secret password.",
    )
    region_name: str = Field(default="us-east-1", description="S3 region.")
    bucket_documents: str = Field(default="documents", description="Bucket for source PDF/DOCX files.")
    bucket_images: str = Field(default="images", description="Bucket for extracted images.")
    presign_ttl_seconds: int = Field(default=3600, gt=0, description="Lifetime of a presigned image link.")

    model_config = SettingsConfigDict(
        env_prefix="S3_",
        env_file=".env",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_storage_settings() -> StorageSettings:
    return StorageSettings()
