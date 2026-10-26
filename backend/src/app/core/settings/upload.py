from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class UploadSettings(BaseSettings):
    max_bytes: int = Field(
        default=52_428_800,  # 50 MB
        gt=0,
        description="Максимальный размер PDF и DOCX файла в байтах (по умолчанию 50 МБ).",
    )
    max_markdown_bytes: int = Field(
        default=5_242_880,  # 5 MB
        gt=0,
        description="Максимальный размер Markdown файла в байтах (по умолчанию 5 МБ).",
    )
    max_pages: int = Field(
        default=300,
        gt=0,
        description="Максимальное количество страниц в документе.",
    )
    max_unzipped_bytes: int = Field(
        default=209_715_200,  # 200 MB
        gt=0,
        description="Максимальный распакованный размер DOCX архива (защита от zip-бомб).",
    )

    model_config = SettingsConfigDict(
        env_prefix="UPLOAD_",
        env_file=".env",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_upload_settings() -> UploadSettings:
    return UploadSettings()
