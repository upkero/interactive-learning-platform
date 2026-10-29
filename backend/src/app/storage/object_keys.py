"""Builders of object keys for both buckets.

Keys must be built only through these functions (story 1.3 rules):
the user-provided file name never becomes part of a key — it lives in
``documents.title``.
"""

from uuid import UUID

# Directory prefixes inside the buckets (match the key layout of story 1.3).
_DOCUMENTS_PREFIX = "documents"
_IMAGES_PREFIX = "images"

PARSED_MARKDOWN_FILENAME = "parsed.md"


def source_key(owner_id: UUID, document_id: UUID, extension: str) -> str:
    """Key of an uploaded source file, e.g. ``documents/<owner>/<doc>/source.pdf``."""
    normalized = _normalized_extension(extension)
    return f"{_DOCUMENTS_PREFIX}/{owner_id}/{document_id}/source.{normalized}"


def parsed_markdown_key(owner_id: UUID, document_id: UUID) -> str:
    """Key of the normalized Markdown produced by the pipeline (story 1.9)."""
    return f"{_DOCUMENTS_PREFIX}/{owner_id}/{document_id}/{PARSED_MARKDOWN_FILENAME}"


def image_key(document_id: UUID, number: int) -> str:
    """Key of an extracted image, e.g. ``images/<doc>/img_1.png`` (story 1.9)."""
    if number < 1:
        raise ValueError("Image number must be 1-based.")
    return f"{_IMAGES_PREFIX}/{document_id}/img_{number}.png"


def _normalized_extension(extension: str) -> str:
    """Lowercase, trimmed extension; anything else is a key-injection risk."""
    stripped = extension.strip().lstrip(".").lower()
    if not stripped or any(char.isspace() for char in stripped) or "/" in stripped or "\\" in stripped:
        raise ValueError(f"Invalid source file extension: {extension!r}")
    return stripped
