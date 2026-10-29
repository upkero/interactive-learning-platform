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
    """documents/{owner}/{doc}/source.{ext}; user file name never enters."""
    owner_id, document_id = uuid4(), uuid4()
    assert source_key(owner_id, document_id, "pdf") == f"documents/{owner_id}/{document_id}/source.pdf"


def test_source_key_normalizes_extension() -> None:
    owner_id, document_id = uuid4(), uuid4()
    assert source_key(owner_id, document_id, ".DOCX") == f"documents/{owner_id}/{document_id}/source.docx"


@pytest.mark.parametrize("extension", ["", "   ", "a/b", "pa th", "\\evil"])
def test_source_key_rejects_bad_extensions(extension: str) -> None:
    with pytest.raises(ValueError):
        source_key(uuid4(), uuid4(), extension)


def test_parsed_markdown_key() -> None:
    owner_id, document_id = uuid4(), uuid4()
    assert parsed_markdown_key(owner_id, document_id) == (
        f"documents/{owner_id}/{document_id}/{PARSED_MARKDOWN_FILENAME}"
    )
    assert PARSED_MARKDOWN_FILENAME == "parsed.md"


def test_image_key_layout() -> None:
    document_id = uuid4()
    assert image_key(document_id, 1) == f"images/{document_id}/img_1.png"
    assert image_key(document_id, 42) == f"images/{document_id}/img_42.png"


def test_image_key_is_one_based() -> None:
    with pytest.raises(ValueError):
        image_key(uuid4(), 0)
