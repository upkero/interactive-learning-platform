from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True, slots=True)
class ExtractedImage:
    ref: str
    data: bytes
    media_type: str
    page: int | None = None
    caption: str | None = None


@dataclass(frozen=True, slots=True)
class ParsedDocument:
    markdown: str
    images: tuple[ExtractedImage, ...] = ()
    page_count: int | None = None
    title: str | None = None
    heading_pages: tuple[tuple[str, int], ...] = ()


class DocumentParser(ABC):
    supported_mime_types: ClassVar[frozenset[str]]

    @abstractmethod
    def parse(self, data: bytes, *, filename: str) -> ParsedDocument:
        """Parse bytes synchronously; callers must move this to a worker thread."""


class ParserRegistry:
    def __init__(self, parsers: tuple[DocumentParser, ...]) -> None:
        self._parsers = parsers

    def for_mime(self, mime: str) -> DocumentParser:
        normalized = mime.split(";", 1)[0].strip().lower()
        for parser in self._parsers:
            if normalized in parser.supported_mime_types:
                return parser
        raise ValueError(f"Unsupported document MIME type: {mime}")
