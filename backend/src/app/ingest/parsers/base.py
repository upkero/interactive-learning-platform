from abc import ABC, abstractmethod
from typing import ClassVar

from src.app.contracts.ingest import ExtractedImage as ExtractedImage
from src.app.contracts.ingest import ParsedDocument as ParsedDocument
from src.app.exceptions.ingest import ParseError


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
        raise ParseError(f"Unsupported document MIME type: {mime}")
