"""Generation service: plan preview (story 1.4.6) and start (story 1.4.7).

``plan`` is a pure read: it loads the parsed tree, runs the splitting
rules (1.10 later replaced through ``PartPlanner``) over the selected
topics and reports the cost against the quota — without reserving or
writing anything. ``start`` does the same inside one transaction, then
reserves quota, creates the parts and only after the commit enqueues
them.
"""

from collections.abc import Callable
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.contracts.documents import DocumentRecord, DocumentStatus, MaterialRole, PartDraft, PartRecord, PartStatus
from src.app.contracts.documents.generation import GenerationAnswers, GenerationStarted
from src.app.core.settings.processing import ProcessingSettings
from src.app.exceptions.documents import DocumentNotFoundError, DocumentNotReadyError
from src.app.interfaces.repositories.documents import (
    DocumentPartRepositoryProtocol,
    DocumentRepositoryProtocol,
    UserMaterialRepositoryProtocol,
)
from src.app.interfaces.repositories.users import UserRepositoryProtocol
from src.app.interfaces.services.task_dispatcher import TaskDispatcher
from src.app.services.documents.processing_capacity import assert_processing_capacity
from src.app.services.documents.splitting import PlannedPart, TopicPlan, TopicTreePlanner
from src.app.services.quota.quota_ledger import QuotaLedger

# the plan preview is meaningful for the same states as the tree read
_READABLE_STATUSES = (DocumentStatus.PARSED, DocumentStatus.DONE)


class GenerationService:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        documents: Callable[[AsyncSession], DocumentRepositoryProtocol],
        materials: Callable[[AsyncSession], UserMaterialRepositoryProtocol],
        parts: Callable[[AsyncSession], DocumentPartRepositoryProtocol],
        users: Callable[[AsyncSession], UserRepositoryProtocol],
        planner: TopicTreePlanner,
        ledger: QuotaLedger,
        dispatcher: TaskDispatcher,
        settings: ProcessingSettings,
    ) -> None:
        self._session_factory = session_factory
        self._documents = documents
        self._materials = materials
        self._parts = parts
        self._users = users
        self._planner = planner
        self._ledger = ledger
        self._dispatcher = dispatcher
        self._settings = settings

    async def start(
        self,
        *,
        user_id: UUID,
        document_id: UUID,
        topic_ids: list[str],
        answers: GenerationAnswers,
    ) -> GenerationStarted:
        async with self._session_factory() as session, session.begin():
            materials = self._materials(session)
            if await materials.get_role(user_id, document_id) is not MaterialRole.OWNER:
                raise DocumentNotFoundError()
            # Lock before reading the document to serialize concurrent starts.
            documents = self._documents(session)
            await assert_processing_capacity(
                users=self._users(session),
                documents=documents,
                owner_id=user_id,
                limit=self._settings.max_active_documents,
                exclude_document_id=document_id,
            )
            plan, _ = await self._plan_with_session(session, user_id, document_id, topic_ids)
            parts = self._parts(session)
            existing = await parts.list_by_document(document_id)
            document = await documents.get(document_id)
            if document is None:
                raise DocumentNotFoundError()
            subtrees = _topic_subtrees(document.topic_tree or {"topics": []})
            next_index = max((part.index for part in existing), default=-1) + 1
            profile = answers.as_dict()
            drafts = [
                PartDraft(
                    index=next_index + part.index,
                    title=part.title,
                    topic_ids=list(part.topic_ids),
                    source_markdown="\n\n".join(
                        p.source_markdown
                        for p in existing
                        if p.status is not PartStatus.FAILED
                        and any(set(p.topic_ids) & subtrees[topic] for topic in part.topic_ids)
                    ),
                    token_count=part.tokens,
                    profile=profile,
                )
                for part in plan.parts
            ]
            if any(not draft.source_markdown.strip() for draft in drafts):
                raise DocumentNotReadyError(detail="Source text for selected topics is not available.")
            quota = await self._ledger.reserve(
                session,
                user_id=user_id,
                document_id=document_id,
                parts=len(plan.parts),
            )
            created = await parts.add_many(document_id, drafts)
            await documents.set_status(document_id, DocumentStatus.GENERATING)
            await self._users(session).save_last_answers(user_id, profile)
        for index, part in enumerate(created):
            await self._dispatcher.enqueue_part(part.id, high=index == 0)
        return GenerationStarted(document_id, tuple(p.id for p in created), len(created), quota.available)

    async def plan(self, *, user_id: UUID, document_id: UUID, topic_ids: list[str]) -> tuple[TopicPlan, int]:
        """The part preview for the selected topics and the remaining quota.

        Nothing is reserved or written: the quota journal is untouched
        and two consecutive calls with the same topics return the same
        answer. Only the owner may plan (404 otherwise, no 403).
        """
        async with self._session_factory() as session:
            return await self._plan_with_session(session, user_id, document_id, topic_ids)

    async def _plan_with_session(
        self,
        session: AsyncSession,
        user_id: UUID,
        document_id: UUID,
        topic_ids: list[str],
    ) -> tuple[TopicPlan, int]:
        role = await self._materials(session).get_role(user_id, document_id)
        if role is not MaterialRole.OWNER:
            raise DocumentNotFoundError()
        document = await self._documents(session).get(document_id)
        if document is None:  # a dangling material row must not crash the read
            raise DocumentNotFoundError()
        self._assert_plannable(document)

        readable = [
            part
            for part in await self._parts(session).list_by_document(document_id)
            if part.status is not PartStatus.FAILED
        ]
        tree = document.topic_tree or {"topics": []}
        tokens_by_topic = _tokens_by_topic(tree, readable)

        plan = self._planner.plan(tree, topic_ids, tokens_by_topic)
        available = (await self._ledger.available(session, user_id=user_id)).available
        return plan, available

    @staticmethod
    def _assert_plannable(document: DocumentRecord) -> None:
        if document.status is DocumentStatus.FAILED:
            raise DocumentNotReadyError(extra={"status": "failed", "reason": document.error or "parse_failed"})
        if document.status not in _READABLE_STATUSES:
            raise DocumentNotReadyError(extra={"status": document.status.value})


def _topic_subtrees(topic_tree: dict[str, Any]) -> dict[str, set[str]]:
    subtrees: dict[str, set[str]] = {}

    def walk(node: dict[str, Any]) -> set[str]:
        descendants = {str(node["id"])}
        for child in node.get("children", []):
            descendants.update(walk(child))
        subtrees[str(node["id"])] = descendants
        return descendants

    for root in topic_tree.get("topics", []):
        walk(root)
    return subtrees


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
