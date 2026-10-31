"""Unit tests 1.3.3: content-based file inspection against fixture files."""

import hashlib
from pathlib import Path

import pytest

from src.app.core.settings.upload import UploadSettings
from src.app.exceptions.documents import FileTooLargeError, TooManyPagesError, UnsupportedFileTypeError
from src.app.services.documents.file_inspector import (
    DOCX,
    MARKDOWN,
    PDF,
    FileInspector,
    InspectedFile,
)

pytestmark = pytest.mark.unit

FILES_DIR = Path(__file__).resolve().parents[3] / "support" / "fixtures" / "files"


def _load(name: str) -> bytes:
    return (FILES_DIR / name).read_bytes()


async def inspect(name: str, settings: UploadSettings | None = None) -> InspectedFile:
    """Inspect the committed fixture through the public async API."""
    inspector = FileInspector(settings or UploadSettings())
    return await inspector.inspect(_load(name), name)


@pytest.mark.parametrize(
    ("fixture", "expected_mime"),
    [
        ("sample.pdf", PDF),
        ("sample.docx", DOCX),
        ("notes.md", MARKDOWN),
    ],
)
async def test_real_files_are_recognized_by_content(fixture: str, expected_mime: str) -> None:
    result = await inspect(fixture)
    assert result.mime_type == expected_mime
    assert result.size_bytes == len(_load(fixture))
    assert result.checksum == hashlib.sha256(_load(fixture)).hexdigest()


async def test_pdf_field_values() -> None:
    result = await inspect("sample.pdf")
    assert result.extension == "pdf"
    assert result.page_count == 1


async def test_docx_pages_read_from_app_xml() -> None:
    result = await inspect("sample.docx")
    assert result.extension == "docx"
    assert result.page_count == 3


async def test_markdown_has_no_page_count() -> None:
    result = await inspect("notes.md")
    assert result.extension == "md"
    assert result.page_count is None


async def test_evil_pdf_actually_png_is_rejected() -> None:
    with pytest.raises(UnsupportedFileTypeError) as exc_info:
        await inspect("evil.pdf")
    assert exc_info.value.status_code == 415
    assert exc_info.value.error_code == "unsupported_file_type"


async def test_empty_file_is_rejected() -> None:
    with pytest.raises(UnsupportedFileTypeError):
        await inspect("empty.bin")


async def test_encrypted_pdf_is_rejected() -> None:
    with pytest.raises(UnsupportedFileTypeError) as exc_info:
        await inspect("encrypted.pdf")
    assert "Encrypted" in exc_info.value.detail


async def test_broken_pdf_is_rejected() -> None:
    with pytest.raises(UnsupportedFileTypeError) as exc_info:
        await inspect("broken.pdf")
    assert "Broken PDF" in exc_info.value.detail


async def test_docx_without_document_xml_is_rejected() -> None:
    with pytest.raises(UnsupportedFileTypeError) as exc_info:
        await inspect("docx_missing_parts.docx")
    assert "word/document.xml" in exc_info.value.detail


async def test_markdown_with_nul_byte_is_rejected() -> None:
    with pytest.raises(UnsupportedFileTypeError):
        await inspect("zero_bytes.md")


async def test_markdown_with_invalid_utf8_is_rejected() -> None:
    with pytest.raises(UnsupportedFileTypeError):
        await inspect("notes_bad_utf8.md")


async def test_pdf_over_size_limit_is_413() -> None:
    settings = UploadSettings(max_bytes=100)
    with pytest.raises(FileTooLargeError) as exc_info:
        await inspect("sample.pdf", settings)
    assert exc_info.value.status_code == 413
    assert exc_info.value.error_code == "file_too_large"


async def test_markdown_over_markdown_limit_is_413() -> None:
    settings = UploadSettings(max_markdown_bytes=10)
    with pytest.raises(FileTooLargeError):
        await inspect("notes.md", settings)


async def test_docx_with_unzipped_over_limit_is_413() -> None:
    """Zip-bomb guard: the limit applies to the unpacked content."""
    settings = UploadSettings(max_unzipped_bytes=200)
    with pytest.raises(FileTooLargeError) as exc_info:
        await inspect("sample.docx", settings)
    assert exc_info.value.status_code == 413
    assert exc_info.value.error_code == "file_too_large"


async def test_pdf_over_page_limit_is_422() -> None:
    with pytest.raises(TooManyPagesError) as exc_info:
        await inspect("pages_301.pdf")
    assert exc_info.value.status_code == 422
    assert exc_info.value.error_code == "too_many_pages"


async def test_stream_oversized_aborts_early_with_413() -> None:
    """The stream must be abandoned right after limit+1 byte, not fully read."""
    chunk = b"x" * (1024 * 1024)
    reads: list[int] = []

    class FakeStream:
        async def read(self, size: int) -> bytes:
            reads.append(size)
            return chunk if len(reads) <= 1_048_576 else b""  # "endless" stream

    inspector = FileInspector(UploadSettings())
    with pytest.raises(FileTooLargeError):
        await inspector.read_with_limit(FakeStream(), max_bytes=2 * 1024 * 1024)

    # 2 MiB allowed, aborted on the third 1 MiB chunk: the gigabytes of
    # tail were never pulled out of the stream
    assert len(reads) == 3


async def test_stream_reads_smaller_than_limit_completely() -> None:
    class FakeStream:
        def __init__(self) -> None:
            self._chunks = [b"a" * 1000, b"b" * 1000, b""]

        async def read(self, size: int) -> bytes:
            return self._chunks.pop(0)

    inspector = FileInspector(UploadSettings())
    data = await inspector.read_with_limit(FakeStream(), max_bytes=1024 * 1024)
    assert data == b"a" * 1000 + b"b" * 1000
