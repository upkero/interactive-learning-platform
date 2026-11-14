from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DocumentsSettings(BaseSettings):
    processing_max_active_documents: int = Field(
        default=2,
        gt=0,
        description=(
            "How many documents of one user may be in processing at the same "
            "time (uploaded but not yet parsed, parsing, generating). "
            "A third one answers 429 processing_limit_reached (story 1.4.13)."
        ),
    )

    model_config = SettingsConfigDict(
        env_prefix="",
        env_file=".env",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_documents_settings() -> DocumentsSettings:
    return DocumentsSettings()
