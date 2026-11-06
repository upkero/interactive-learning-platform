"""Unit tests of object key builders (story 1.3 rules)."""

from uuid import uuid4

import pytest

from src.app.storage.object_keys import (
    PARSED_MARKDOWN_FILENAME,
    image_key,
    parsed_markdown_key,
    source_key,
)

pytestmark = pytest.mark.unit


def test_source_key_layout() -> None:
    """{owner}/{doc}/source.{ext} — no directory prefixes (lead's decision)."""
    owner_id, document_id = uuid4(), uuid4()
    assert source_key(owner_id, document_id, "pdf") == f"{owner_id}/{document_id}/source.pdf"


def test_source_key_normalizes_extension() -> None:
    owner_id, document_id = uuid4(), uuid4()
    assert source_key(owner_id, document_id, ".DOCX") == f"{owner_id}/{document_id}/source.docx"


@pytest.mark.parametrize(
    "extension",
    ["", "   ", "a/b", "pa th", "\\evil", "p.df", "p\ndf", "pdf#x", "пдф"],
)
def test_source_key_rejects_bad_extensions(extension: str) -> None:
    """Only the ASCII alnum whitelist of real extensions survives.

    (``pdf\\n`` is not here: outer whitespace is normalized away into
    the perfectly valid ``pdf``.)
    """
    with pytest.raises(ValueError):
        source_key(uuid4(), uuid4(), extension)


def test_parsed_markdown_key() -> None:
    owner_id, document_id = uuid4(), uuid4()
    assert parsed_markdown_key(owner_id, document_id) == f"{owner_id}/{document_id}/{PARSED_MARKDOWN_FILENAME}"
    assert PARSED_MARKDOWN_FILENAME == "parsed.md"


def test_image_key_layout() -> None:
    document_id = uuid4()
    assert image_key(document_id, 1) == f"{document_id}/img_1.png"
    assert image_key(document_id, 42) == f"{document_id}/img_42.png"


def test_image_key_is_one_based() -> None:
    with pytest.raises(ValueError):
        image_key(uuid4(), 0)
