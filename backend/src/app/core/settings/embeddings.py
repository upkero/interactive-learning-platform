"""Embedding settings (story 2.3).

The provider is a deployment choice: ``bge_m3`` runs locally on CPU and is
the default, ``voyage`` calls the paid API. Both produce 1024-dimensional
vectors, so one pgvector column serves either model.

The cache lives in a separate Redis database (``/2`` by default) so that
flushing it cannot touch the Celery broker or progress streams. The model
name is part of every cache key; switching providers does not require a
cache flush, only ``python -m src.cli reembed-descriptions`` for the table.
"""

from functools import lru_cache
from typing import Literal, Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

EmbeddingsProvider = Literal["bge_m3", "voyage"]


class EmbeddingsSettings(BaseSettings):
    provider: EmbeddingsProvider = Field(
        default="bge_m3",
        description="Embedding model: bge_m3 (local, CPU) or voyage (API).",
    )
    device: str = Field(default="cpu", description="Torch device for the local model.")
    batch_size: int = Field(default=32, ge=1, description="Texts per embedder call.")
    cache_ttl_days: int = Field(default=30, ge=1, description="Lifetime of one cached vector.")
    cache_redis_url: str = Field(
        default="redis://localhost:6379/2",
        description="Redis database for the embedding cache (not the broker).",
    )
    voyage_api_key: SecretStr | None = Field(
        default=None,
        validation_alias="VOYAGE_API_KEY",
        description="Voyage API key; required only for the voyage provider.",
    )

    @property
    def cache_ttl_seconds(self) -> int:
        return self.cache_ttl_days * 24 * 3600

    @model_validator(mode="after")
    def validate_voyage_key(self) -> Self:
        if self.provider == "voyage" and (self.voyage_api_key is None or not self.voyage_api_key.get_secret_value()):
            raise ValueError("VOYAGE_API_KEY is required when EMBEDDINGS_PROVIDER=voyage")
        return self

    model_config = SettingsConfigDict(env_prefix="EMBEDDINGS_", env_file=".env", extra="ignore")


@lru_cache(maxsize=1)
def get_embeddings_settings() -> EmbeddingsSettings:
    return EmbeddingsSettings()
