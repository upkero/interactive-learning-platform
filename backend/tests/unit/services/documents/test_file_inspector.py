"""Content-based file inspection: committed fixture files plus synthetic PDF/DOCX bombs."""

import hashlib
import zipfile
from io import BytesIO

import pytest
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from src.app.core.settings.upload import UploadSettings
from src.app.exceptions.documents import FileTooLargeError, TooManyPagesError, UnsupportedFileTypeError
from src.app.services.documents.file_inspector import (
    DOCX,
    MARKDOWN,
    PDF,
    FileInspector,
    InspectedFile,
)
from tests.support.fixtures.documents import (
    APP_XML,
    CONTENT_TYPES,
    WIDE_CATCH_FIXTURES,
    blank_pages_pdf,
    docx_archive,
    docx_bomb_bytes,
    flip_crc,
    load,
    patch_file_size_to_one,
    pdf_mutants,
    reversed_central_directory,
)

pytestmark = pytest.mark.unit


async def inspect(name: str, settings: UploadSettings | None = None) -> InspectedFile:
    """Inspect the committed fixture through the public async API."""
    inspector = FileInspector(settings or UploadSettings())
    return await inspector.inspect(load(name), name)


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
    assert result.size_bytes == len(load(fixture))
    assert result.checksum == hashlib.sha256(load(fixture)).hexdigest()


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


@pytest.mark.parametrize("mutant_name", sorted(pdf_mutants()))
async def test_corrupted_pdf_mutation_is_415_not_500(mutant_name: str) -> None:
    """Any parser exception on corrupted bytes is a 415, not a 500.

    Each mutant exercises only the failure class pypdf actually raises
    for it: if that class escapes the handler net, the raw exception
    surfaces in this test instead of satisfying ``pytest.raises`` —
    the mutant cannot be dodged by a prediction, the inspector must
    genuinely catch what the bytes produce.
    """
    data = pdf_mutants()[mutant_name]
    inspector = FileInspector(UploadSettings())
    with pytest.raises(UnsupportedFileTypeError) as exc_info:
        await inspector.inspect(data, mutant_name)
    assert exc_info.value.status_code == 415
    assert exc_info.value.detail == "Broken PDF."


@pytest.mark.parametrize(("fixture", "exception_class"), WIDE_CATCH_FIXTURES)
async def test_wide_pdf_catch_survives_classes_outside_pypdf_family(fixture: str, exception_class: type) -> None:
    """Each fixture is pinned to the exception class pypdf rejects it with.

    The first assertion runs against pypdf directly: if a fixture ever
    stops raising its designated class (parser update, fixture rot), the
    test fails here instead of silently passing a widened handler.
    The second assertion is the actual guarantee: without the wide catch the
    class would escape the inspector as a 500.
    """
    data = load(fixture)
    with pytest.raises(exception_class) as probe:
        reader = PdfReader(BytesIO(data))
        _ = len(reader.pages)  # lazy page-tree load: the read path _inspect_pdf uses
    assert not isinstance(probe.value, PdfReadError) or exception_class is PdfReadError

    inspector = FileInspector(UploadSettings())
    with pytest.raises(UnsupportedFileTypeError) as exc_info:
        await inspector.inspect(data, fixture)
    assert exc_info.value.status_code == 415
    assert exc_info.value.detail == "Broken PDF."


async def test_markdown_name_with_pdf_magic_is_unsupported_type() -> None:
    """PDF bytes under a .md name: wrong type, not "Broken PDF."."""
    inspector = FileInspector(UploadSettings())
    with pytest.raises(UnsupportedFileTypeError) as exc_info:
        await inspector.inspect(load("sample.pdf"), "report.md")
    assert exc_info.value.detail == "Unsupported file type."


async def test_zip_bomb_with_honest_headers_is_413() -> None:
    """An honest bomb unpacking to 200 MB + 1 must hit the unzipped limit."""
    settings = UploadSettings()  # defaults: max_unzipped_bytes = 200 MB
    bomb = docx_bomb_bytes(settings.max_unzipped_bytes + 1)
    assert len(bomb) < settings.max_bytes  # wire side is inside the 50 MB limit
    with pytest.raises(FileTooLargeError) as exc_info:
        await FileInspector(settings).inspect(bomb, "zip_bomb.docx")
    assert exc_info.value.status_code == 413
    assert exc_info.value.error_code == "file_too_large"


async def test_zip_bomb_with_fake_headers_is_413() -> None:
    """file_size=1 in local and central headers must not save the bomb."""
    bomb = patch_file_size_to_one(docx_bomb_bytes(UploadSettings().max_unzipped_bytes + 1), "word/document.xml")
    with pytest.raises(FileTooLargeError) as exc_info:
        await FileInspector(UploadSettings()).inspect(bomb, "zip_bomb.docx")
    assert exc_info.value.status_code == 413


async def test_tampered_crc_is_broken_docx_415() -> None:
    """A CRC mismatch during member reading is a 415, never a 500."""
    archive = docx_archive(
        {
            "[Content_Types].xml": CONTENT_TYPES,
            "word/document.xml": b"<w:document/>",
            "docProps/app.xml": APP_XML,
        }
    )
    tampered = flip_crc(archive, "docProps/app.xml")
    with pytest.raises(UnsupportedFileTypeError) as exc_info:
        await FileInspector(UploadSettings()).inspect(tampered, "tampered.docx")
    assert "Broken DOCX" in exc_info.value.detail
    assert exc_info.value.status_code == 415


async def test_valid_docx_with_shuffled_central_directory_passes() -> None:
    """A valid DOCX whose central-directory records are shuffled must load.

    ZIP does not order central-directory records by file offset, so a
    shuffled-but-valid archive must be accepted. zipfile writes the
    records in member order, and shuffling them keeps the archive valid
    (``zipfile.testzip()`` and ``unzip -t`` accept it); the inspector
    must order members by file offset, not record order.
    """
    valid = docx_archive(
        {
            "[Content_Types].xml": CONTENT_TYPES,
            "word/document.xml": b"<w:document/>",
            "docProps/app.xml": APP_XML,
        }
    )
    shuffled = reversed_central_directory(valid)
    with zipfile.ZipFile(BytesIO(shuffled)) as archive:
        names = [info.filename for info in archive.infolist()]
        assert names == ["docProps/app.xml", "word/document.xml", "[Content_Types].xml"]
        assert archive.testzip() is None

    result = await FileInspector(UploadSettings()).inspect(shuffled, "shuffled.docx")
    assert result.page_count == 3


async def test_zip_bomb_with_shuffled_central_directory_is_rejected() -> None:
    """Ordering members by file offset must route the shuffled bomb to 413.

    With a deterministic file-offset order the bomb hits its size cap
    and answers 413. Accepting 415 here as well would let a broken
    ordering slip back — the members would overlap into empty payload
    slices and surface as "Broken DOCX" — without this test noticing, so
    only 413 is accepted on purpose.
    """
    bomb = reversed_central_directory(docx_bomb_bytes(UploadSettings().max_unzipped_bytes + 1))
    with pytest.raises(FileTooLargeError) as exc_info:
        await FileInspector(UploadSettings()).inspect(bomb, "zip_bomb.docx")
    assert exc_info.value.status_code == 413


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


@pytest.fixture
def pages_301_pdf_bytes() -> bytes:
    """301-page PDF built at test time: such files never sit in git."""
    return blank_pages_pdf(301)


async def test_pdf_over_page_limit_is_422(pages_301_pdf_bytes: bytes) -> None:
    with pytest.raises(TooManyPagesError) as exc_info:
        await FileInspector(UploadSettings()).inspect(pages_301_pdf_bytes, "many_pages.pdf")
    assert exc_info.value.status_code == 422
    assert exc_info.value.error_code == "too_many_pages"


async def test_pdf_exactly_at_page_limit_passes() -> None:
    """The page limit is inclusive: 300 pages fit the default settings."""
    result = await FileInspector(UploadSettings()).inspect(blank_pages_pdf(300), "pages_300.pdf")
    assert result.page_count == 300


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
