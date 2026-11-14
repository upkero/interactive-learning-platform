"""Read-side queries for documents (stories 1.4.3 and 1.4.5).

``GET /documents/{id}`` resolves access through ``user_materials``:
no material row — 404 ``document_not_found``, so a foreign document is
indistinguishable from a missing one. ``shared_with`` is only populated
for the owner; the source link is a presigned URL for uploads and the
original gdocs link for imports.

``GET /documents/{id}/topics`` (1.4.5) returns the parse result tree
with a token sum per node: a node counts each part once even when the
part belongs to several topics of the subtree.
"""

from typing import Any
from uuid import UUID

from src.app.contracts.documents import (
    DocumentDetails,
    DocumentRecord,
    DocumentStatus,
    MaterialRole,
    PartRecord,
    PartStatus,
    SourceType,
)
from src.app.exceptions.documents import DocumentNotFoundError, DocumentNotReadyError
from src.app.interfaces.repositories.documents import (
    DocumentPartRepositoryProtocol,
    DocumentRepositoryProtocol,
    UserMaterialRepositoryProtocol,
)
from src.app.interfaces.storage.object_storage_client import ObjectStorageClient

# statuses from which the topic tree is readable; parse result of
# ``uploaded``/``parsing`` documents does not exist yet
_READABLE_STATUSES = (DocumentStatus.PARSED, DocumentStatus.DONE)


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

    async def get_topic_tree(self, *, user_id: UUID, document_id: UUID) -> dict[str, Any]:
        """The parsed topic tree of an accessible document (story 1.4.5).

        Returns ``{"topics": [node, ...]}`` where every node carries
        ``{id, title, level, tokens, children}`` and ``tokens`` is the
        token sum of the parts in the whole subtree (a part is counted
        once even when it belongs to several topics of the subtree).
        Raises ``DocumentNotReadyError`` (409) while the document is
        still processing, with the current status in ``extra`` — or,
        for ``failed`` documents, with the parse error as the detail.
        """
        role = await self._materials.get_role(user_id, document_id)
        if role is None:
            raise DocumentNotFoundError()
        document = await self._documents.get(document_id)
        if document is None:  # a dangling material row must not crash the read
            raise DocumentNotFoundError()

        self._assert_parsed(document)

        tree = document.topic_tree or {"topics": []}
        parts = await self._parts.list_by_document(document_id)
        readable = [part for part in parts if part.status is not PartStatus.FAILED]
        nodes = [_build_node(node, readable, level=1)[0] for node in tree["topics"]]
        return {"topics": nodes}

    @staticmethod
    def _assert_parsed(document: DocumentRecord) -> None:
        if document.status is DocumentStatus.FAILED:
            raise DocumentNotReadyError(detail=document.error or "The document parsing failed.")
        if document.status not in _READABLE_STATUSES:
            raise DocumentNotReadyError(extra={"status": document.status.value})


def _build_node(
    node: dict[str, Any],
    parts: list[PartRecord],
    *,
    level: int,
) -> tuple[dict[str, Any], set[str]]:
    """Convert one raw topic node; returns the output node and its subtree topic ids.

    ``tokens`` is the token sum of the readable parts in the whole
    subtree: a part counts once if any of its topics falls inside the
    subtree, even when it is assigned to several topics of it.
    """
    subtree_ids: set[str] = {str(node["id"])}
    children: list[dict[str, Any]] = []
    for raw_child in node.get("children", []):
        child, child_ids = _build_node(raw_child, parts, level=level + 1)
        children.append(child)
        subtree_ids |= child_ids

    tokens = sum(part.token_count for part in parts if subtree_ids & set(part.topic_ids))
    return (
        {
            "id": str(node["id"]),
            "title": str(node["title"]),
            "level": level,
            "tokens": tokens,
            "children": children,
        },
        subtree_ids,
    )


__all__ = ["DocumentQueryService"]
