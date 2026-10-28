from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class UploadSettings(BaseSettings):
    max_bytes: int = Field(
        default=52_428_800,  # 50 MB
        gt=0,
        description="Maximum size of a PDF or DOCX file in bytes (default 50 MB).",
    )
    max_markdown_bytes: int = Field(
        default=5_242_880,  # 5 MB
        gt=0,
        description="Maximum size of a Markdown file in bytes (default 5 MB).",
    )
    max_pages: int = Field(
        default=300,
        gt=0,
        description="Maximum number of pages in a document.",
    )
    max_unzipped_bytes: int = Field(
        default=209_715_200,  # 200 MB
        gt=0,
        description="Maximum unzipped DOCX archive size (zip-bomb protection).",
    )

    model_config = SettingsConfigDict(
        env_prefix="UPLOAD_",
        env_file=".env",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_upload_settings() -> UploadSettings:
    return UploadSettings()
