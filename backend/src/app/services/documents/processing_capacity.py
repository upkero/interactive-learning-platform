"""The documents-in-processing limit (story 1.4.13).

A document is in processing while the pipeline still has to work on it:
``uploaded`` (not taken by the worker yet), ``parsing`` or ``generating``.
The check runs inside the write transaction right after
``users.lock_for_update`` — the row lock serializes parallel requests, so
two simultaneous uploads cannot both pass the count.

The limit itself comes from ``ProcessingSettings`` through the service
constructor; this helper is pure logic over the already-bound
repositories.
"""

from uuid import UUID

from src.app.exceptions.documents import ProcessingLimitError
from src.app.interfaces.repositories.documents import DocumentRepositoryProtocol
from src.app.interfaces.repositories.users import UserRepositoryProtocol


async def assert_processing_capacity(
    *,
    users: UserRepositoryProtocol,
    documents: DocumentRepositoryProtocol,
    owner_id: UUID,
    limit: int,
    exclude_document_id: UUID | None = None,
) -> None:
    """Lock the user's row and refuse one document over the limit."""
    await users.lock_for_update(owner_id)
    active = await documents.count_active(owner_id, exclude=exclude_document_id)
    if active >= limit:
        raise ProcessingLimitError(extra={"limit": limit})


__all__ = ["assert_processing_capacity"]
