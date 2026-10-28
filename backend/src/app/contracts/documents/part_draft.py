"""Typed input for inserting new document parts (replaces raw dicts)."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class PartDraft:
    """Data for a new document_parts row; the repository owns the defaults."""

    index: int
    title: str
    topic_ids: list[str]
    source_markdown: str
    token_count: int
    profile: dict[str, Any] | None = None
    content: dict[str, Any] | None = None
