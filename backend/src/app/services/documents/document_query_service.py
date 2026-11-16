"""Read-side queries for documents (stories 1.4.3 and 1.4.5).

``GET /documents/{id}`` resolves access through ``user_materials``:
no material row — 404 ``document_not_found``, so a foreign document is
indistinguishable from a missing one. ``shared_with`` is only populated
for the owner; the source link is a presigned URL for uploads and the
original gdocs link for imports.

``GET /documents/{id}/topics`` (1.4.5) returns the parse result tree as
stored by the parser (story 1.9): ``level`` and ``tokens`` are copied
from ``TopicNode.level``/``total_tokens`` and never recalculated here.
"""

from collections.abc import Callable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.contracts.documents import (
    DocumentDetails,
    DocumentRecord,
    DocumentStatus,
    MaterialRole,
    SourceType,
    TopicNode,
)
from src.app.exceptions.documents import DocumentNotFoundError, DocumentNotReadyError
from src.app.interfaces.repositories.documents import (
    DocumentPartRepositoryProtocol,
    DocumentRepositoryProtocol,
    UserMaterialRepositoryProtocol,
)
from src.app.interfaces.storage.object_storage_client import ObjectStorageClient

# statuses from which the topic tree is readable; the parse result of
# ``uploaded``/``parsing`` documents does not exist yet
READABLE_STATUSES = frozenset({DocumentStatus.PARSED, DocumentStatus.DONE})


class DocumentQueryService:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        documents: Callable[[AsyncSession], DocumentRepositoryProtocol],
        materials: Callable[[AsyncSession], UserMaterialRepositoryProtocol],
        parts: Callable[[AsyncSession], DocumentPartRepositoryProtocol],
        storage: ObjectStorageClient,
    ) -> None:
        self._session_factory = session_factory
        self._documents = documents
        self._materials = materials
        self._parts = parts
        self._storage = storage

    async def get_document(self, *, user_id: UUID, document_id: UUID) -> DocumentDetails:
        async with self._session_factory() as session:
            materials = self._materials(session)
            role = await materials.get_role(user_id, document_id)
            if role is None:
                raise DocumentNotFoundError()
            document = await self._documents(session).get(document_id)
            if document is None:  # a dangling material row must not crash the read
                raise DocumentNotFoundError()
            parts = await self._parts(session).list_by_document(document_id)
            shared_with = tuple(await materials.list_shared_with(document_id)) if role is MaterialRole.OWNER else ()
        return DocumentDetails(
            document=document,
            role=role,
            source_url=self._source_url(document),
            parts=tuple(parts),
            shared_with=shared_with,
        )

    def _source_url(self, document: DocumentRecord) -> str | None:
        if document.source_type is SourceType.GDOCS:
            return document.source_uri
        return self._storage.presign_get_url(bucket="documents", key=document.object_key)

    async def get_topic_tree(self, *, user_id: UUID, document_id: UUID) -> tuple[TopicNode, ...]:
        """The parsed topic tree of an accessible document (story 1.4.5)."""
        async with self._session_factory() as session:
            role = await self._materials(session).get_role(user_id, document_id)
            if role is None:
                raise DocumentNotFoundError()
            document = await self._documents(session).get(document_id)
            if document is None:  # a dangling material row must not crash the read
                raise DocumentNotFoundError()
        self._assert_parsed(document)
        return document.topic_tree or ()

    @staticmethod
    def _assert_parsed(document: DocumentRecord) -> None:
        """Refuse the tree of a document that has none (409).

        ``failed`` documents carry the parse error code in ``extra`` under
        the unified error format: the client translates the code, never
        the human text.
        """
        if document.status is DocumentStatus.FAILED:
            reason = document.error_code.value if document.error_code is not None else None
            raise DocumentNotReadyError(
                detail="Document processing failed.", extra={"status": "failed", "reason": reason}
            )
        if document.status not in READABLE_STATUSES:
            raise DocumentNotReadyError(extra={"status": document.status.value})


__all__ = ["READABLE_STATUSES", "DocumentQueryService"]
