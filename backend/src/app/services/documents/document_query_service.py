"""Read-side queries for documents (story 1.4.3).

``GET /documents/{id}`` resolves access through ``user_materials``:
no material row — 404 ``document_not_found``, so a foreign document is
indistinguishable from a missing one. ``shared_with`` is only populated
for the owner; the source link is a presigned URL for uploads and the
original gdocs link for imports.
"""

from uuid import UUID

from src.app.contracts.documents import (
    DocumentDetails,
    DocumentRecord,
    MaterialRole,
    SourceType,
)
from src.app.exceptions.documents import DocumentNotFoundError
from src.app.interfaces.repositories.documents import (
    DocumentPartRepositoryProtocol,
    DocumentRepositoryProtocol,
    UserMaterialRepositoryProtocol,
)
from src.app.interfaces.storage.object_storage_client import ObjectStorageClient


class DocumentQueryService:
    def __init__(
        self,
        *,
        documents: DocumentRepositoryProtocol,
        materials: UserMaterialRepositoryProtocol,
        parts: DocumentPartRepositoryProtocol,
        storage: ObjectStorageClient,
    ) -> None:
        self._documents = documents
        self._materials = materials
        self._parts = parts
        self._storage = storage

    async def get_document(self, *, user_id: UUID, document_id: UUID) -> DocumentDetails:
        role = await self._materials.get_role(user_id, document_id)
        if role is None:
            raise DocumentNotFoundError()
        document = await self._documents.get(document_id)
        if document is None:  # a dangling material row must not crash the read
            raise DocumentNotFoundError()
        parts = await self._parts.list_by_document(document_id)
        shared_with = tuple(await self._materials.list_shared_with(document_id)) if role is MaterialRole.OWNER else ()
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


__all__ = ["DocumentQueryService"]
