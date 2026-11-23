from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class IngestSettings(BaseSettings):
    tokens_encoding: str = "o200k_base"
    tokens_calibration: float = Field(default=1.15, gt=0)
    segment_max_tokens: int = Field(default=12000, gt=0)
    gdocs_max_bytes: int = Field(default=52_428_800, gt=0)
    max_images: int = Field(default=40, gt=0)
    model_config = SettingsConfigDict(env_prefix="INGEST_", env_file=".env", extra="ignore")


@lru_cache(maxsize=1)
def get_ingest_settings() -> IngestSettings:
    return IngestSettings()
