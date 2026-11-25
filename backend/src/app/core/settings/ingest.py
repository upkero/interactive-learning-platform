from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class IngestSettings(BaseSettings):
    tokens_encoding: str = Field(default="o200k_base", validation_alias="TOKENS_ENCODING")
    tokens_calibration: float = Field(default=1.15, gt=0, validation_alias="TOKENS_CALIBRATION")
    segment_max_tokens: int = Field(default=22000, gt=0, validation_alias="SPLIT_MAX_TOKENS")
    docling_artifacts_path: str | None = None
    max_images: int = Field(default=40, gt=0)
    image_concurrency: int = Field(default=4, gt=0)
    model_config = SettingsConfigDict(env_prefix="INGEST_", env_file=".env", extra="ignore")


@lru_cache(maxsize=1)
def get_ingest_settings() -> IngestSettings:
    return IngestSettings()
