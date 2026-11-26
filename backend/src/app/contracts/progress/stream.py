"""Shared progress stream naming."""

from uuid import UUID


def stream_key(document_id: UUID) -> str:
    return f"progress:{document_id}"
