"""Settings of the documents-in-processing limit (story 1.4.13)."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ProcessingSettings(BaseSettings):
    max_active_documents: int = Field(
        default=2,
        gt=0,
        description=(
            "How many documents of one user may be in processing at the same "
            "time (uploaded but not yet parsed, parsing, generating). "
            "One more answers 429 processing_limit_reached (story 1.4.13)."
        ),
    )

    model_config = SettingsConfigDict(
        env_prefix="PROCESSING_",
        env_file=".env",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_processing_settings() -> ProcessingSettings:
    return ProcessingSettings()
