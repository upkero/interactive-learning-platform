"""Generation service: plan preview (story 1.4.6), start (1.4.7 later).

``plan`` is a pure read: it loads the parsed topic tree, runs the
splitting rules (1.10) over the selected topics and reports the cost
against the quota — without reserving or writing anything.
"""

from typing import Any
from uuid import UUID

from src.app.contracts.documents import DocumentRecord, DocumentStatus, MaterialRole, PartRecord, PartStatus
from src.app.exceptions.documents import DocumentNotFoundError, DocumentNotReadyError
from src.app.interfaces.repositories.documents import (
    DocumentPartRepositoryProtocol,
    DocumentRepositoryProtocol,
    UserMaterialRepositoryProtocol,
)
from src.app.services.documents.splitting import PlannedPart, TopicPlan, TopicTreePlanner
from src.app.services.quota.ledger import QuotaLedger

# the plan preview is meaningful for the same states as the tree read
_READABLE_STATUSES = (DocumentStatus.PARSED, DocumentStatus.DONE)


class GenerationService:
    def __init__(
        self,
        *,
        documents: DocumentRepositoryProtocol,
        materials: UserMaterialRepositoryProtocol,
        parts: DocumentPartRepositoryProtocol,
        planner: TopicTreePlanner,
        ledger: QuotaLedger,
    ) -> None:
        self._documents = documents
        self._materials = materials
        self._parts = parts
        self._planner = planner
        self._ledger = ledger

    async def plan(self, *, user_id: UUID, document_id: UUID, topic_ids: list[str]) -> tuple[TopicPlan, int]:
        """The part preview for the selected topics and the remaining quota.

        Nothing is reserved or written: the quota journal is untouched
        and two consecutive calls with the same topics return the same
        answer. Only the owner may plan (404 otherwise, no 403).
        """
        role = await self._materials.get_role(user_id, document_id)
        if role is not MaterialRole.OWNER:
            raise DocumentNotFoundError()
        document = await self._documents.get(document_id)
        if document is None:  # a dangling material row must not crash the read
            raise DocumentNotFoundError()
        self._assert_plannable(document)

        readable = [
            part for part in await self._parts.list_by_document(document_id) if part.status is not PartStatus.FAILED
        ]
        tree = document.topic_tree or {"topics": []}
        tokens_by_topic = _tokens_by_topic(tree, readable)

        plan = self._planner.plan(tree, topic_ids, tokens_by_topic)
        available = await self._ledger.available(user_id)
        return plan, available

    @staticmethod
    def _assert_plannable(document: DocumentRecord) -> None:
        if document.status is DocumentStatus.FAILED:
            raise DocumentNotReadyError(detail=document.error or "The document parsing failed.")
        if document.status not in _READABLE_STATUSES:
            raise DocumentNotReadyError(extra={"status": document.status.value})


def _tokens_by_topic(
    topic_tree: dict[str, Any],
    parts: list[PartRecord],
) -> dict[str, int]:
    """Subtree token sum of every topic (same rule as the 1.4.5 read).

    A part counts once towards a topic when the topic's subtree touches
    any of the part's topics — no double counting at nested levels.
    """
    sums: dict[str, int] = {}

    def walk(node: dict[str, Any]) -> set[str]:
        subtree: set[str] = {str(node["id"])}
        for child in node.get("children", []):
            subtree |= walk(child)
        sums[str(node["id"])] = sum(part.token_count for part in parts if subtree & set(part.topic_ids))
        return subtree

    for root in topic_tree.get("topics", []):
        walk(root)
    return sums


__all__ = ["GenerationService", "PlannedPart"]
