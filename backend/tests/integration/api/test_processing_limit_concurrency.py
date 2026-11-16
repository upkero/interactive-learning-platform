"""The row lock enforces the active-document limit under concurrency."""

import asyncio
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.contracts.documents import DocumentStatus, MaterialRole, SourceType
from src.app.contracts.documents.generation import GenerationAnswers, GenerationCommand
from src.app.core.clock import SystemClock
from src.app.core.settings.processing import ProcessingSettings
from src.app.exceptions.documents import ProcessingLimitError
from src.app.repositories.document_part_repository import DocumentPartRepository
from src.app.repositories.document_repository import DocumentRepository
from src.app.repositories.generation_ledger_repository import GenerationLedgerRepository
from src.app.repositories.user_material_repository import UserMaterialRepository
from src.app.repositories.user_repository import UserRepository
from src.app.services.documents.generation_service import GenerationService
from src.app.services.documents.topic_per_part_planner import TopicPerPartPlanner
from src.app.services.quota.quota_ledger import QuotaLedger
from src.app.storage.object_keys import parsed_markdown_key
from tests.support.fakes.services.task_dispatcher import FakeTaskDispatcher
from tests.support.fakes.storage.object_storage_client import FakeObjectStorageClient

pytestmark = pytest.mark.integration


async def test_three_parallel_generations_only_two_start(session_factory: async_sessionmaker[AsyncSession]) -> None:
    ids: list[UUID] = []
    async with session_factory() as session, session.begin():
        users = UserRepository(session)
        user = await users.create(email="concurrent@example.com", password_hash="hash")
        for index in range(3):
            documents = DocumentRepository(session)
            doc = await documents.create(
                owner_id=user.id,
                title=f"doc {index}",
                source_type=SourceType.UPLOAD,
                object_key=f"{index}.md",
                mime_type="text/markdown",
                size_bytes=1,
                checksum="a" * 64,
            )
            await UserMaterialRepository(session).create(user_id=user.id, document_id=doc.id, role=MaterialRole.OWNER)
            await documents.set_status(doc.id, DocumentStatus.PARSED)
            await documents.set_topic_tree(doc.id, [{"id": "t", "title": "T", "start": 0, "end": 4, "total_tokens": 1}])
            ids.append(doc.id)
    dispatcher = FakeTaskDispatcher()
    storage = FakeObjectStorageClient()
    for doc_id in ids:
        await storage.put_object(
            bucket="documents", key=parsed_markdown_key(user.id, doc_id), data=b"text", content_type="text/markdown"
        )

    async def start(doc_id: UUID) -> bool:
        service = GenerationService(
            session_factory=session_factory,
            documents=DocumentRepository,
            materials=UserMaterialRepository,
            parts=DocumentPartRepository,
            users=UserRepository,
            planner=TopicPerPartPlanner(),
            storage=storage,
            ledger=QuotaLedger(
                users_factory=UserRepository,
                ledger_factory=GenerationLedgerRepository,
                clock=SystemClock(),
            ),
            dispatcher=dispatcher,
            settings=ProcessingSettings(max_active_documents=2),
        )
        try:
            await service.start(
                GenerationCommand(
                    user_id=user.id,
                    document_id=doc_id,
                    topic_ids=("t",),
                    answers=GenerationAnswers(level="novice", goal="exam", depth="standard"),
                )
            )
        except ProcessingLimitError:
            return False
        return True

    results = await asyncio.gather(*(start(doc_id) for doc_id in ids))
    assert sorted(results) == [False, True, True]
    assert len(dispatcher.calls) == 2
    async with session_factory() as session:
        assert await DocumentRepository(session).count_active(user.id) == 2
