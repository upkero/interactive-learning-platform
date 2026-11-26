"""Generation service: plan preview (story 1.4.6) and start (story 1.4.7).

``plan`` is a pure read: it loads the parsed tree, runs ``PartPlanner`` over the selected
topics and reports the cost against the quota — without reserving or
writing anything. ``start`` does the same inside one transaction, then
reserves quota, creates the parts and only after the commit enqueues
them.
"""

import asyncio
import logging
from collections.abc import Callable
from uuid import UUID

from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.contracts.documents import (
    DocumentRecord,
    DocumentStatus,
    MaterialRole,
    PartDraft,
    TopicNode,
)
from src.app.contracts.documents.generation import GenerationCommand, GenerationStarted
from src.app.contracts.documents.topic_plan import TopicPlan
from src.app.core.settings.processing import ProcessingSettings
from src.app.exceptions.documents import (
    DocumentNotFoundError,
    DocumentNotReadyError,
    EmptyTopicSelectionError,
    UnknownTopicError,
)
from src.app.interfaces.notifications.claims import NotificationClaims
from src.app.interfaces.repositories.documents import (
    DocumentPartRepositoryProtocol,
    DocumentRepositoryProtocol,
    UserMaterialRepositoryProtocol,
)
from src.app.interfaces.repositories.users import UserRepositoryProtocol
from src.app.interfaces.services.part_planner import PartPlanner
from src.app.interfaces.services.progress_notifier import ProgressNotifier
from src.app.interfaces.services.task_dispatcher import TaskDispatcher
from src.app.interfaces.storage.object_storage_client import ObjectStorageClient
from src.app.services.documents.document_query_service import READABLE_STATUSES
from src.app.services.documents.processing_capacity import assert_processing_capacity
from src.app.services.quota.quota_ledger import QuotaLedger
from src.app.storage.object_keys import parsed_markdown_key

logger = logging.getLogger(__name__)


class GenerationService:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        documents: Callable[[AsyncSession], DocumentRepositoryProtocol],
        materials: Callable[[AsyncSession], UserMaterialRepositoryProtocol],
        parts: Callable[[AsyncSession], DocumentPartRepositoryProtocol],
        users: Callable[[AsyncSession], UserRepositoryProtocol],
        planner: PartPlanner,
        storage: ObjectStorageClient,
        ledger: QuotaLedger,
        dispatcher: TaskDispatcher,
        settings: ProcessingSettings,
        notification_claims: NotificationClaims,
        progress_notifier: ProgressNotifier,
    ) -> None:
        self._session_factory = session_factory
        self._documents = documents
        self._materials = materials
        self._parts = parts
        self._users = users
        self._planner = planner
        self._storage = storage
        self._ledger = ledger
        self._dispatcher = dispatcher
        self._settings = settings
        self._notification_claims = notification_claims
        self._progress_notifier = progress_notifier

    async def start(self, command: GenerationCommand) -> GenerationStarted:
        user_id, document_id, topic_ids, answers = (
            command.user_id,
            command.document_id,
            command.topic_ids,
            command.answers,
        )
        markdown = await self._load_markdown(user_id, document_id)
        async with self._session_factory() as session, session.begin():
            # Lock before reading the document to serialize concurrent starts.
            documents = self._documents(session)
            await assert_processing_capacity(
                users=self._users(session),
                documents=documents,
                owner_id=user_id,
                limit=self._settings.max_active_documents,
                exclude_document_id=document_id,
            )
            plan, _ = await self._plan_with_session(session, user_id, document_id, topic_ids, markdown)
            parts = self._parts(session)
            existing = await parts.list_by_document(document_id)
            next_index = max((part.index for part in existing), default=-1) + 1
            profile = answers.as_dict()
            if any(not part.markdown.strip() for part in plan.parts):
                raise DocumentNotReadyError(detail="Source text for selected topics is not available.")
            quota = await self._ledger.reserve(
                session,
                user_id=user_id,
                document_id=document_id,
                parts=len(plan.parts),
            )
            drafts = [
                PartDraft(
                    index=next_index + part.index,
                    title=part.title,
                    topic_ids=list(part.topic_ids),
                    source_markdown=part.markdown,
                    token_count=part.tokens,
                    quota_period_start=quota.period.start,
                    profile=profile,
                )
                for part in plan.parts
            ]
            created = await parts.add_many(document_id, drafts)
            await documents.set_generation_start(document_id, next_index)
            await documents.set_status(document_id, DocumentStatus.GENERATING)
            await self._users(session).save_last_answers(user_id, profile)
        try:
            await self._notification_claims.reset(document_id)
        except RedisError:
            logger.warning("notification.reset_failed", extra={"document_id": str(document_id)}, exc_info=True)
        await self._progress_notifier.reset(document_id)
        for index, part in enumerate(created):
            await self._dispatcher.enqueue_part(part.id, high=index == 0)
        return GenerationStarted(document_id, tuple(p.id for p in created), len(created), quota.available)

    async def plan(self, *, user_id: UUID, document_id: UUID, topic_ids: list[str]) -> tuple[TopicPlan, int]:
        """The part preview for the selected topics and the remaining quota.

        Nothing is reserved or written: the quota journal is untouched
        and two consecutive calls with the same topics return the same
        answer. Only the owner may plan (404 otherwise, no 403).
        """
        markdown = await self._load_markdown(user_id, document_id)
        async with self._session_factory() as session:
            return await self._plan_with_session(session, user_id, document_id, topic_ids, markdown)

    async def _plan_with_session(
        self,
        session: AsyncSession,
        user_id: UUID,
        document_id: UUID,
        topic_ids: list[str] | tuple[str, ...],
        markdown: str,
    ) -> tuple[TopicPlan, int]:
        role = await self._materials(session).get_role(user_id, document_id)
        if role is not MaterialRole.OWNER:
            raise DocumentNotFoundError()
        document = await self._documents(session).get(document_id)
        if document is None:  # a dangling material row must not crash the read
            raise DocumentNotFoundError()
        self._assert_plannable(document)

        tree = document.topic_tree or ()
        if not topic_ids:
            raise EmptyTopicSelectionError()

        def ids(nodes: tuple[TopicNode, ...]) -> set[str]:
            return {node.id for node in nodes} | {item for node in nodes for item in ids(node.children)}

        if set(topic_ids) - ids(tree):
            raise UnknownTopicError()
        parts = await asyncio.to_thread(self._planner.plan, tree, set(topic_ids), markdown)
        plan = TopicPlan(tuple(parts))
        available = (await self._ledger.available(session, user_id=user_id)).available
        return plan, available

    @staticmethod
    def _assert_plannable(document: DocumentRecord) -> None:
        if document.status is DocumentStatus.FAILED:
            # Parsing failures remain unavailable, but failed generation parts
            # may be retried against the already parsed source and topic tree.
            if document.error_code is None and document.topic_tree:
                return
            reason = document.error_code.value if document.error_code is not None else None
            raise DocumentNotReadyError(
                detail="Document processing failed.", extra={"status": "failed", "reason": reason}
            )
        if document.status not in READABLE_STATUSES:
            raise DocumentNotReadyError(extra={"status": document.status.value})

    async def _load_markdown(self, user_id: UUID, document_id: UUID) -> str:
        # Authorize before touching storage; check again in the transaction.
        async with self._session_factory() as session:
            if await self._materials(session).get_role(user_id, document_id) is not MaterialRole.OWNER:
                raise DocumentNotFoundError()
            document = await self._documents(session).get(document_id)
            if document is None:
                raise DocumentNotFoundError()
            self._assert_plannable(document)
            key = parsed_markdown_key(document.owner_id, document.id)
        return (await self._storage.get_object(bucket="documents", key=key)).decode("utf-8")


__all__ = ["GenerationService"]
