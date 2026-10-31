"""Content-based file inspection (story 1.3.3).

Neither the extension nor the client ``Content-Type`` is trusted: the
``Content-Type`` may only be logged, what counts is what the bytes are.
PDF is recognized by the ``%PDF-`` signature, DOCX by the ``PK\x03\x04``
zip signature plus required archive members, Markdown by a valid UTF-8
silhouette without NUL bytes and a text extension.

Heavy work (``pypdf``, ``zipfile``) runs in a worker thread via
``asyncio.to_thread`` so the event loop never blocks. Errors surface as
``UnsupportedFileTypeError`` (415), ``FileTooLargeError`` (413) or
``TooManyPagesError`` (422).
"""

import asyncio
import hashlib
import re
import zipfile
from dataclasses import dataclass
from io import BytesIO
from typing import Protocol

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from src.app.core.settings.upload import UploadSettings
from src.app.exceptions.documents import FileTooLargeError, TooManyPagesError, UnsupportedFileTypeError

PDF = "application/pdf"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
MARKDOWN = "text/markdown"

_ZIP_MAGIC = b"PK\x03\x04"
_PDF_MAGIC = b"%PDF-"
# docProps/app.xml of a DOCX may declare <Pages>; a stale value is only
# pre-check evidence, the authoritative cut is token-based in 1.9
_APP_PAGES = re.compile(rb"<Pages>(\d+)</Pages>")
_CHUNK_SIZE = 1024 * 1024  # 1 MiB per read for streaming uploads

_DOCX_REQUIRED_MEMBERS = ("[Content_Types].xml", "word/document.xml")


class UploadStream(Protocol):
    """Anything readable in chunks, e.g. Starlette's ``UploadFile``."""

    async def read(self, size: int) -> bytes: ...


@dataclass(frozen=True, slots=True)
class InspectedFile:
    """Result of the inspection, feeds the documents table row."""

    mime_type: str
    extension: str
    size_bytes: int
    page_count: int | None
    checksum: str


class FileInspector:
    """Validates an uploaded file against ``UploadSettings`` limits."""

    def __init__(self, settings: UploadSettings) -> None:
        self._s = settings

    async def inspect(self, data: bytes, filename: str | None) -> InspectedFile:
        """Inspect file content off the event loop; filename is a hint only."""
        return await asyncio.to_thread(self._inspect, data, (filename or "").lower())

    async def read_with_limit(self, stream: UploadStream, *, max_bytes: int) -> bytes:
        """Read a stream in chunks, aborting as soon as the limit is passed.

        The rule from story 1.3: never buffer an oversized file in full —
        the stream stops after ``limit + 1`` bytes and raises 413 without
        reading the remaining (possibly gigabytes of) upload.
        """
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = await stream.read(_CHUNK_SIZE)
            if not chunk:
                break
            total += len(chunk)
            chunks.append(chunk)
            if total > max_bytes:
                raise FileTooLargeError(f"The file exceeds {max_bytes} bytes.")
        return b"".join(chunks)

    def _inspect(self, data: bytes, filename: str) -> InspectedFile:
        if not data:
            raise UnsupportedFileTypeError("Empty file.")
        checksum = hashlib.sha256(data).hexdigest()

        if data.startswith(_PDF_MAGIC):
            return self._inspect_pdf(data, checksum)
        if data.startswith(_ZIP_MAGIC):
            # a zip is only accepted when it really is a DOCX package:
            # _check_docx rejects archives without the required members
            return self._inspect_docx(data, checksum)

        if filename.endswith((".md", ".markdown")) and b"\x00" not in data:
            self._check_size(len(data), self._s.max_markdown_bytes)
            try:
                data.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise UnsupportedFileTypeError("Invalid UTF-8 in Markdown file.") from exc
            return InspectedFile(MARKDOWN, "md", len(data), None, checksum)

        raise UnsupportedFileTypeError()

    def _inspect_pdf(self, data: bytes, checksum: str) -> InspectedFile:
        self._check_size(len(data), self._s.max_bytes)
        try:
            reader = PdfReader(BytesIO(data))
            if reader.is_encrypted:
                raise UnsupportedFileTypeError("Encrypted PDF is not supported.")
            pages = len(reader.pages)
        except PdfReadError as exc:
            raise UnsupportedFileTypeError("Broken PDF.") from exc
        self._check_pages(pages)
        return InspectedFile(PDF, "pdf", len(data), pages, checksum)

    def _inspect_docx(self, data: bytes, checksum: str) -> InspectedFile:
        self._check_size(len(data), self._s.max_bytes)
        pages = self._check_docx(data)
        return InspectedFile(DOCX, "docx", len(data), pages, checksum)

    def _check_docx(self, data: bytes) -> int | None:
        """Validate the archive: members, unzipped size, optional Pages."""
        try:
            with zipfile.ZipFile(BytesIO(data)) as archive:
                names = set(archive.namelist())
                for member in _DOCX_REQUIRED_MEMBERS:
                    if member not in names:
                        raise UnsupportedFileTypeError(f"DOCX is missing {member}.")

                unzipped_total = sum(info.file_size for info in archive.infolist())
                self._check_size(unzipped_total, self._s.max_unzipped_bytes)

                app_xml = archive.read("docProps/app.xml") if "docProps/app.xml" in names else b""
        except zipfile.BadZipFile as exc:
            raise UnsupportedFileTypeError("Broken DOCX archive.") from exc

        match = _APP_PAGES.search(app_xml)
        if match is None:
            return None
        pages = int(match.group(1))
        self._check_pages(pages)
        return pages

    def _check_size(self, size_bytes: int, limit: int) -> None:
        if size_bytes > limit:
            raise FileTooLargeError(f"The file exceeds {limit} bytes.")

    def _check_pages(self, pages: int) -> None:
        if pages > self._s.max_pages:
            raise TooManyPagesError(f"The document has {pages} pages (limit {self._s.max_pages}).")
