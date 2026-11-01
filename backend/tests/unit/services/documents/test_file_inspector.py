"""Unit tests 1.3.3: content-based file inspection against fixture files."""

import hashlib
import struct
import zipfile
from io import BytesIO
from pathlib import Path

import pytest
from pypdf import PdfWriter

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


def _pdf_mutants() -> dict[str, bytes]:
    """Corruptions of sample.pdf (review B3), deterministic by construction.

    pypdf parses in lenient mode, so random byte mutations are tolerated
    more often than not. The mutations below therefore land on structural
    anchors of the committed file: the indirect-reference operand of the
    ``/Pages 2 0 R`` catalog entry, the object dictionary opener, and the
    trailing structure halved away. Every mutant self-verifies — the
    parametrized test below fails if the parser still swallows it.
    """
    valid = _load("sample.pdf")
    r_pos = valid.index(b"/Pages 2 0 R") + 10  # the "R" operand itself
    dict_pos = valid.index(b"<<\n/Type")
    return {
        "flipped_byte.pdf": valid[:r_pos] + bytes([valid[r_pos] ^ 0xFF]) + valid[r_pos + 1 :],
        "truncated.pdf": valid[: len(valid) // 2],
        "junk_inserted.pdf": valid[:dict_pos] + b"\x00junk\x00" * 8 + valid[dict_pos:],
    }


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


@pytest.mark.parametrize("mutant_name", sorted(_pdf_mutants()))
async def test_corrupted_pdf_mutation_is_415_not_500(mutant_name: str) -> None:
    """Any parser exception on corrupted bytes is a 415 (review B3).

    If a mutant's failure class escapes the handler net, the test itself
    crashes instead of passing — the mutants self-verify the handling.
    """
    data = _pdf_mutants()[mutant_name]
    inspector = FileInspector(UploadSettings())
    with pytest.raises(UnsupportedFileTypeError) as exc_info:
        await inspector.inspect(data, mutant_name)
    assert exc_info.value.status_code == 415
    assert exc_info.value.detail == "Broken PDF."


async def test_markdown_name_with_pdf_magic_is_unsupported_type() -> None:
    """PDF bytes under a .md name: wrong type, not "Broken PDF." (review 6)."""
    inspector = FileInspector(UploadSettings())
    with pytest.raises(UnsupportedFileTypeError) as exc_info:
        await inspector.inspect(_load("sample.pdf"), "report.md")
    assert exc_info.value.detail == "Unsupported file type."


# --- DOCX archive builders (review V1/V2: zip bombs, header lies, CRC) ---

_CONTENT_TYPES = (
    b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    b'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"></Types>'
)

_APP_XML = (
    b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    b'<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">'
    b"<Pages>3</Pages></Properties>"
)

# local header: sig(4) version(2) flags(2) method(2) time(2) date(2) crc(4) csize(4) usize(4)
_LOCAL_CRC, _LOCAL_UNPACKED_SIZE = 14, 22
# central record: sig(4) vmade(2) vneed(2) flags(2) method(2) time(2) date(2) crc(4) csize(4) usize(4)
_CENTRAL_CRC, _CENTRAL_UNPACKED_SIZE = 16, 24


def _docx_archive(members: dict[str, bytes]) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, payload in members.items():
            archive.writestr(name, payload)
    return buffer.getvalue()


def _docx_bomb_bytes(target: int) -> bytes:
    """DOCX that unpacks to ``target`` bytes; deflates far below the 50 MB wire limit.

    Build is streamed through ``archive.open(..., "w")`` so the payload
    never sits in memory as one large bytes object.
    """
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _CONTENT_TYPES)
        with archive.open("word/document.xml", "w") as member:
            chunk = b"\x00" * (1024 * 1024)
            for _ in range(target // len(chunk)):
                member.write(chunk)
            member.write(b"\x00" * (target % len(chunk)))
    return buffer.getvalue()


def _header_offsets(archive_bytes: bytes, member: str) -> tuple[int, int]:
    """Local header offset and central-record offset of one member."""
    with zipfile.ZipFile(BytesIO(archive_bytes)) as archive:
        infos = archive.infolist()
        index = [info.filename for info in infos].index(member)
        local_offset = infos[index].header_offset
    central_positions: list[int] = []
    cursor = -1
    for _ in infos:  # central records appear in the same order as infolist()
        cursor = archive_bytes.find(b"PK\x01\x02", cursor + 1)
        central_positions.append(cursor)
    return local_offset, central_positions[index]


def _patch_file_size_to_one(archive_bytes: bytes, member: str) -> bytes:
    """Declare ``file_size=1`` in both headers (review V2 fake-header bomb).

    With the lie in place a naive ``sum(file_size)`` sees about nothing;
    header-trusting streaming reads are the trap equally: zipfile clamps
    reads by ``file_size``, so only a header-blind re-count can catch it.
    """
    data = bytearray(archive_bytes)
    local, central = _header_offsets(archive_bytes, member)
    struct.pack_into("<I", data, local + _LOCAL_UNPACKED_SIZE, 1)
    struct.pack_into("<I", data, central + _CENTRAL_UNPACKED_SIZE, 1)
    return bytes(data)


def _flip_crc(archive_bytes: bytes, member: str) -> bytes:
    """Corrupt the stored CRC of one member in both headers (review V1)."""
    data = bytearray(archive_bytes)
    local, central = _header_offsets(archive_bytes, member)
    data[local + _LOCAL_CRC] ^= 0xFF
    data[central + _CENTRAL_CRC] ^= 0xFF
    return bytes(data)


async def test_zip_bomb_with_honest_headers_is_413() -> None:
    """An honest bomb unpacking to 200 MB + 1 must hit the unzipped limit."""
    settings = UploadSettings()  # defaults: max_unzipped_bytes = 200 MB
    bomb = _docx_bomb_bytes(settings.max_unzipped_bytes + 1)
    assert len(bomb) < settings.max_bytes  # wire side is inside the 50 MB limit
    with pytest.raises(FileTooLargeError) as exc_info:
        await FileInspector(settings).inspect(bomb, "zip_bomb.docx")
    assert exc_info.value.status_code == 413
    assert exc_info.value.error_code == "file_too_large"


async def test_zip_bomb_with_fake_headers_is_413() -> None:
    """file_size=1 in local and central headers must not save the bomb (V2)."""
    bomb = _patch_file_size_to_one(_docx_bomb_bytes(UploadSettings().max_unzipped_bytes + 1), "word/document.xml")
    with pytest.raises(FileTooLargeError) as exc_info:
        await FileInspector(UploadSettings()).inspect(bomb, "zip_bomb.docx")
    assert exc_info.value.status_code == 413


async def test_tampered_crc_is_broken_docx_415() -> None:
    """A CRC mismatch during member reading is a 415, never a 500 (V1)."""
    archive = _docx_archive(
        {
            "[Content_Types].xml": _CONTENT_TYPES,
            "word/document.xml": b"<w:document/>",
            "docProps/app.xml": _APP_XML,
        }
    )
    tampered = _flip_crc(archive, "docProps/app.xml")
    with pytest.raises(UnsupportedFileTypeError) as exc_info:
        await FileInspector(UploadSettings()).inspect(tampered, "tampered.docx")
    assert "Broken DOCX" in exc_info.value.detail
    assert exc_info.value.status_code == 415


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
    """301-page PDF built at test time (review 6): never sits in git."""
    buffer = BytesIO()
    writer = PdfWriter()
    for _ in range(301):
        writer.add_blank_page(width=612, height=792)
    writer.write(buffer)
    return buffer.getvalue()


async def test_pdf_over_page_limit_is_422(pages_301_pdf_bytes: bytes) -> None:
    with pytest.raises(TooManyPagesError) as exc_info:
        await FileInspector(UploadSettings()).inspect(pages_301_pdf_bytes, "many_pages.pdf")
    assert exc_info.value.status_code == 422
    assert exc_info.value.error_code == "too_many_pages"


async def test_pdf_exactly_at_page_limit_passes() -> None:
    """The page limit is inclusive: 300 pages fit the default settings."""
    buffer = BytesIO()
    writer = PdfWriter()
    for _ in range(300):
        writer.add_blank_page(width=612, height=792)
    writer.write(buffer)
    result = await FileInspector(UploadSettings()).inspect(buffer.getvalue(), "pages_300.pdf")
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
