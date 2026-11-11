"""Content-based file inspection (story 1.3.3).

Neither the extension nor the client ``Content-Type`` is trusted: the
``Content-Type`` may only be logged, what counts is what the bytes are.
PDF is recognized by the ``%PDF-`` signature, DOCX by the ``PK\x03\x04``
zip signature plus required archive members, Markdown by valid UTF-8
text without NUL bytes carrying a text extension.

Heavy work (``pypdf``, ``zipfile``) runs in a worker thread via
``asyncio.to_thread`` so the event loop never blocks. Errors surface as
``UnsupportedFileTypeError`` (415), ``FileTooLargeError`` (413) or
``TooManyPagesError`` (422).
"""

import asyncio
import hashlib
import re
import struct
import zipfile
import zlib
from dataclasses import dataclass
from io import BytesIO
from typing import Protocol

from pypdf import PdfReader
from pypdf.errors import PdfReadError, PyPdfError

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

# pypdf raises PdfReadError for classic corruption, but mutated xref tables
# or content streams may also surface as bare ValueError/KeyError/etc. from
# its internals (and runaway recursion from deeply nested structures), so
# the net is intentionally wide: broken bytes are a client 415, never a 500.
_BROKEN_PDF_ERRORS = (PdfReadError, PyPdfError, ValueError, TypeError, KeyError, AttributeError, RecursionError)

_DOCX_REQUIRED_MEMBERS = ("[Content_Types].xml", "word/document.xml")
_MEMBER_CHUNK = 64 * 1024  # compressed slice per feed so the output cap bites early


def _local_data_start(archive_bytes: bytes, info: zipfile.ZipInfo) -> int:
    """Offset of a member's payload: local header plus its name/extra fields.

    The central directory only places the member; the local header
    carries its own (possibly different) name and extra field lengths,
    so they are read from the raw bytes, never from declared sizes.
    """
    if archive_bytes[info.header_offset : info.header_offset + 4] != _ZIP_MAGIC:
        raise UnsupportedFileTypeError("Broken DOCX archive.")
    name_len, extra_len = struct.unpack_from("<HH", archive_bytes, info.header_offset + 26)
    return info.header_offset + 30 + int(name_len) + int(extra_len)


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
        reading the remaining (possibly gigabytes of) upload. Pass
        ``max(settings.max_bytes, settings.max_markdown_bytes)``: the type
        of the upload is only known after inspection, so the reader must
        allow the largest limit first and let ``inspect()`` enforce the
        final one.
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
            if filename.endswith((".md", ".markdown")):
                # a Markdown name around PDF bytes is a wrong-type upload,
                # not a broken one: report the type, not "Broken PDF."
                raise UnsupportedFileTypeError("Unsupported file type.")
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
        except UnsupportedFileTypeError:
            raise  # encrypted: its own message is precise, keep it
        except _BROKEN_PDF_ERRORS as exc:
            raise UnsupportedFileTypeError("Broken PDF.") from exc
        self._check_pages(pages)
        return InspectedFile(PDF, "pdf", len(data), pages, checksum)

    def _inspect_docx(self, data: bytes, checksum: str) -> InspectedFile:
        self._check_size(len(data), self._s.max_bytes)
        pages = self._check_docx(data)
        return InspectedFile(DOCX, "docx", len(data), pages, checksum)

    def _check_docx(self, data: bytes) -> int | None:
        """Validate the archive: members, REAL unpacked size, optional Pages.

        Declared sizes are not trusted: a bomb may claim
        ``file_size=1`` in its local and central headers and dodge naive
        ``sum(file_size)`` checks — and even ``zipfile``'s own streaming
        reads, which it clamps by ``file_size``. Members are instead
        located by offset arithmetic on the raw bytes and their DEFLATE
        streams are decompressed under a hard output cap, aborting the
        moment the cumulative unpacked size passes the limit.
        """
        try:
            archive = zipfile.ZipFile(BytesIO(data))
        except zipfile.BadZipFile as exc:
            raise UnsupportedFileTypeError("Broken DOCX archive.") from exc
        with archive:
            names = set(archive.namelist())
            for member in _DOCX_REQUIRED_MEMBERS:
                if member not in names:
                    raise UnsupportedFileTypeError(f"DOCX is missing {member}.")
            self._check_unzipped_size(data, archive)
            try:
                # ordinary read: zipfile verifies the member CRC here,
                # tampered archives surface as BadZipFile → 415
                app_xml = archive.read("docProps/app.xml") if "docProps/app.xml" in names else b""
            except zipfile.BadZipFile as exc:
                raise UnsupportedFileTypeError("Broken DOCX archive.") from exc

        match = _APP_PAGES.search(app_xml)
        if match is None:
            return None
        pages = int(match.group(1))
        self._check_pages(pages)
        return pages

    def _check_unzipped_size(self, data: bytes, archive: zipfile.ZipFile) -> None:
        """Sum the real unpacked sizes across members, aborting after the limit.

        A member's payload ends where the next member starts (or at the
        central directory), independent of any declared size; DEFLATE
        streams self-terminate so their true end is found by zlib.

        Members are ordered by file offset, not by central-directory
        order: the ZIP spec does not require the two to match, and a
        valid archive whose central-directory records are shuffled must
        not be rejected. Overlap abuse is kept:
        records sharing one offset yield an empty payload slice and fail
        with 415.
        """
        infos = sorted(archive.infolist(), key=lambda info: info.header_offset)
        ends = [info.header_offset for info in infos[1:]] + [archive.start_dir]
        total = 0
        for info, data_end in zip(infos, ends, strict=True):
            start = _local_data_start(data, info)
            if info.compress_type == zipfile.ZIP_STORED:
                total += data_end - start
                self._check_size(total, self._s.max_unzipped_bytes)
            elif info.compress_type == zipfile.ZIP_DEFLATED:
                total += self._decompress_member(data, start, data_end, total)
            else:
                raise UnsupportedFileTypeError("Unsupported DOCX compression.")

    def _decompress_member(self, data: bytes, start: int, end: int, already: int) -> int:
        """Raw-deflate ``[start:end)``; returns its real uncompressed size.

        ``already`` is the unpacked total of the earlier members, so the
        cap cuts in as soon as the cumulative size breaks the limit —
        the whole bomb is never even fully decompressed.
        """
        decompressor = zlib.decompressobj(-zlib.MAX_WBITS)
        produced = 0
        pos = start
        try:
            while not decompressor.eof:
                piece = decompressor.unconsumed_tail or data[pos : min(pos + _MEMBER_CHUNK, end)]
                if not decompressor.unconsumed_tail:
                    pos += len(piece)
                if not piece:
                    # the zlib stream does not end inside the member slice
                    raise UnsupportedFileTypeError("Broken DOCX archive.")
                produced += len(decompressor.decompress(piece, self._s.max_unzipped_bytes - already - produced + 1))
                self._check_size(already + produced, self._s.max_unzipped_bytes)
        except zlib.error as exc:
            raise UnsupportedFileTypeError("Broken DOCX archive.") from exc
        return produced

    def _check_size(self, size_bytes: int, limit: int) -> None:
        if size_bytes > limit:
            raise FileTooLargeError(f"The file exceeds {limit} bytes.")

    def _check_pages(self, pages: int) -> None:
        if pages > self._s.max_pages:
            raise TooManyPagesError(f"The document has {pages} pages (limit {self._s.max_pages}).")
