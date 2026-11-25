"""Ports used by the document-ingestion service."""

from contextlib import AbstractAsyncContextManager
from typing import Protocol
from uuid import UUID

from src.app.contracts.ingest import ExtractedImage
from src.app.ingest.parsers.base import DocumentParser


class ParserResolver(Protocol):
    def for_mime(self, mime: str) -> DocumentParser: ...


class GoogleDocsImporter(Protocol):
    async def fetch(self, url: str) -> tuple[bytes, str | None]: ...


class ImageDescriberProtocol(Protocol):
    async def describe(
        self, images: tuple[ExtractedImage, ...], *, document_context: str = ""
    ) -> dict[str, str | None]: ...


class TopicSegmenterProtocol(Protocol):
    async def segment(self, markdown: str) -> str: ...


class ParsingLease(Protocol):
    """A document-scoped nonblocking lease shared across workers."""

    def acquire(self, document_id: UUID) -> AbstractAsyncContextManager[bool]: ...
