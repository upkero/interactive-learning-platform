"""Typed input for inserting new images (replaces raw dicts)."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ImageDraft:
    """Data for a new images row; the repository owns the defaults."""

    object_key: str
    width: int
    height: int
    page: int | None = None
    caption: str | None = None
    description: str | None = None
    topic_id: str | None = None
