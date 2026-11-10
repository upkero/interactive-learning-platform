"""Builders of synthetic PDF/DOCX fixtures for the file-inspector tests.

Notable pieces:
- ``pdf_mutants``: byte-level corruptions of ``sample.pdf`` (the exact
  mutants are deterministic by construction); the ``broken_pdf_*.pdf``
  wide-catch fixtures are committed binary files (triggering bytes are
  too weak to regenerate), loaded from ``support/fixtures/files/``.
- DOCX builders: honest bombs, header-lie patches, CRC corruption and
  central-directory shuffling, all built from raw zip structures.
"""

import struct
import zipfile
from io import BytesIO
from pathlib import Path

from pypdf import PdfWriter
from pypdf.errors import LimitReachedError

FILES_DIR = Path(__file__).resolve().parent / "files"


def load(name: str) -> bytes:
    """Read one committed binary fixture from ``support/fixtures/files/``."""
    return (FILES_DIR / name).read_bytes()


# (fixture file, exception pypdf raises for it).
# Each fixture makes pypdf raise a class NOT covered by a bare
# ``except PdfReadError`` on the same setup calls
# (``PdfReader(BytesIO(...))`` plus ``len(reader.pages)``)
# that ``FileInspector._inspect_pdf`` performs:
#
# - limit_reached: no /Root and no /Catalog-typed object left in the
#   file, so the recovery scan runs out of its default 10_000-object
#   cap (pypdf raises LimitReachedError, a sibling of PdfReadError
#   under PyPdfError that a narrow catch does not keep);
# - type_error / attribute_error: one structural byte replaced with
#   '/' or '%', surfacing those builtins un-wrapped from the parser;
# - value_error: pypdf int()-parses the startxref offset and the
#   malformed token raises a plain ValueError from inside its core.
#
# So a narrowed ``except PdfReadError`` net fails every fixture below.
WIDE_CATCH_FIXTURES: tuple[tuple[str, type], ...] = (
    ("broken_pdf_limit_reached.pdf", LimitReachedError),
    ("broken_pdf_value_error.pdf", ValueError),
    ("broken_pdf_type_error.pdf", TypeError),
    ("broken_pdf_attribute_error.pdf", AttributeError),
)


def pdf_mutants() -> dict[str, bytes]:
    """Corruptions of sample.pdf, deterministic by construction.

    pypdf parses in lenient mode, so random byte mutations are tolerated
    more often than not. The mutations below therefore land on structural
    anchors of the committed file: the indirect-reference operand of the
    ``/Pages 2 0 R`` catalog entry, the object dictionary opener, and the
    trailing structure halved away.

    Coverage is split honestly: the three generated mutants only exercise
    the 415 mapping (pypdf rejects each with a plain ``PdfReadError``, so
    they would also pass under a bare narrow catch); the wide handler is
    proven by the four ``broken_pdf_*.pdf`` fixtures in
    ``WIDE_CATCH_FIXTURES``, each raising a class a bare
    ``except PdfReadError`` would let escape as a 500. The fixtures are
    committed as binary files because the triggering bytes are too weak
    to find again by generation alone; the class map keeps their
    exception classes pinned per test case.
    """
    valid = load("sample.pdf")
    r_pos = valid.index(b"/Pages 2 0 R") + 10  # the "R" operand itself
    dict_pos = valid.index(b"<<\n/Type")
    return {
        "flipped_byte.pdf": valid[:r_pos] + bytes([valid[r_pos] ^ 0xFF]) + valid[r_pos + 1 :],
        "truncated.pdf": valid[: len(valid) // 2],
        "junk_inserted.pdf": valid[:dict_pos] + b"\x00junk\x00" * 8 + valid[dict_pos:],
        "limit_reached.pdf": load("broken_pdf_limit_reached.pdf"),
        "value_error.pdf": load("broken_pdf_value_error.pdf"),
        "type_error.pdf": load("broken_pdf_type_error.pdf"),
        "attribute_error.pdf": load("broken_pdf_attribute_error.pdf"),
    }


CONTENT_TYPES = (
    b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    b'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"></Types>'
)

APP_XML = (
    b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    b'<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">'
    b"<Pages>3</Pages></Properties>"
)

# local header: sig(4) version(2) flags(2) method(2) time(2) date(2) crc(4) csize(4) usize(4)
LOCAL_CRC_OFFSET = 14
LOCAL_UNPACKED_SIZE_OFFSET = 22
# central record: sig(4) vmade(2) vneed(2) flags(2) method(2) time(2) date(2) crc(4) csize(4) usize(4)
CENTRAL_CRC_OFFSET = 16
CENTRAL_UNPACKED_SIZE_OFFSET = 24


def docx_archive(members: dict[str, bytes]) -> bytes:
    """Build a small valid DOCX-like archive from raw members."""
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, payload in members.items():
            archive.writestr(name, payload)
    return buffer.getvalue()


def docx_bomb_bytes(target: int) -> bytes:
    """DOCX that unpacks to ``target`` bytes; deflates far below the 50 MB wire limit.

    Build is streamed through ``archive.open(..., "w")`` so the payload
    never sits in memory as one large bytes object.
    """
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", CONTENT_TYPES)
        with archive.open("word/document.xml", "w") as member:
            chunk = b"\x00" * (1024 * 1024)
            for _ in range(target // len(chunk)):
                member.write(chunk)
            member.write(b"\x00" * (target % len(chunk)))
    return buffer.getvalue()


def header_offsets(archive_bytes: bytes, member: str) -> tuple[int, int]:
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


def patch_file_size_to_one(archive_bytes: bytes, member: str) -> bytes:
    """Declare ``file_size=1`` in both headers (fake-header bomb).

    With the lie in place a naive ``sum(file_size)`` sees about nothing;
    header-trusting streaming reads are the trap equally: zipfile clamps
    reads by ``file_size``, so only a header-blind re-count can catch it.
    """
    data = bytearray(archive_bytes)
    local, central = header_offsets(archive_bytes, member)
    struct.pack_into("<I", data, local + LOCAL_UNPACKED_SIZE_OFFSET, 1)
    struct.pack_into("<I", data, central + CENTRAL_UNPACKED_SIZE_OFFSET, 1)
    return bytes(data)


def flip_crc(archive_bytes: bytes, member: str) -> bytes:
    """Corrupt the stored CRC of one member in both headers."""
    data = bytearray(archive_bytes)
    local, central = header_offsets(archive_bytes, member)
    data[local + LOCAL_CRC_OFFSET] ^= 0xFF
    data[central + CENTRAL_CRC_OFFSET] ^= 0xFF
    return bytes(data)


def reversed_central_directory(archive_bytes: bytes) -> bytes:
    """Reverse the order of central-directory records of a valid ZIP.

    The ZIP spec does not require central-directory records to follow the
    order of the file's local headers, so a shuffled archive stays valid;
    zipfile writes records in member order, and shuffling them here
    reproduces what third-party generators may emit.
    Records are contiguous between the first ``PK\\x01\\x02`` and the
    end-of-central-directory marker, each ``46 + name + extra + comment``
    bytes long, and their embedded local-header offsets are left intact —
    only the record order changes.
    """
    first = archive_bytes.index(b"PK\x01\x02")
    eocd = archive_bytes.index(b"PK\x05\x06")
    records: list[tuple[int, int]] = []
    cursor = first
    while cursor < eocd:
        name_len, extra_len, comment_len = struct.unpack_from("<HHH", archive_bytes, cursor + 28)
        length = 46 + name_len + extra_len + comment_len
        records.append((cursor, length))
        cursor += length
    assert cursor == eocd  # records are contiguous; nothing sits between them
    replaced = b"".join(archive_bytes[start : start + length] for start, length in reversed(records))
    return archive_bytes[:first] + replaced + archive_bytes[first + len(replaced) :]


def blank_pages_pdf(page_count: int) -> bytes:
    """A PDF with ``page_count`` blank US-Letter pages, built at test time."""
    buffer = BytesIO()
    writer = PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=612, height=792)
    writer.write(buffer)
    return buffer.getvalue()
