"""Parser output independent of implementations."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExtractedImage:
    ref: str
    data: bytes
    media_type: str
    page: int | None = None
    caption: str | None = None
    # Offsets of the inline replacement relative to its normalized paragraph.
    paragraph_span: tuple[int, int] | None = None


@dataclass(frozen=True, slots=True)
class ParsedDocument:
    markdown: str
    images: tuple[ExtractedImage, ...] = ()
    page_count: int | None = None
    title: str | None = None
    heading_pages: tuple[tuple[str, int], ...] = ()
