"""Builders of object keys for both buckets.

Keys must be built only through these functions (story 1.3 rules):
the user-provided file name never becomes part of a key — it lives in
``documents.title``. The layout follows the lead's decision (review):
``{owner_id}/{document_id}/...`` without directory prefixes — bucket
assignment already separates documents from images, and saving on one
prefix avoids the doubled-nesting look of ``documents/documents/...``.
"""

from uuid import UUID

PARSED_MARKDOWN_FILENAME = "parsed.md"


def source_key(owner_id: UUID, document_id: UUID, extension: str) -> str:
    """Key of an uploaded source file, e.g. ``<owner>/<doc>/source.pdf``."""
    normalized = _normalized_extension(extension)
    return f"{owner_id}/{document_id}/source.{normalized}"


def parsed_markdown_key(owner_id: UUID, document_id: UUID) -> str:
    """Key of the normalized Markdown produced by the pipeline (story 1.9)."""
    return f"{owner_id}/{document_id}/{PARSED_MARKDOWN_FILENAME}"


def image_key(document_id: UUID, number: int) -> str:
    """Key of an extracted image, e.g. ``<doc>/img_1.png`` (story 1.9)."""
    if number < 1:
        raise ValueError("Image number must be 1-based.")
    return f"{document_id}/img_{number}.png"


def _normalized_extension(extension: str) -> str:
    """Lowercase, trimmed extension of the ``pdf``/``docx``/``md`` kind.

    Anything outside the ASCII alnum whitelist is a key-injection risk
    (dots create sibling directories, spaces and code points trick the
    pipeline), so it is rejected instead of escaped.
    """
    stripped = extension.strip().lstrip(".").lower()
    if not stripped or not (stripped.isascii() and stripped.isalnum()):
        raise ValueError(f"Invalid source file extension: {extension!r}")
    return stripped
