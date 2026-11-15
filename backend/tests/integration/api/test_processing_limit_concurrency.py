"""The row lock enforces the active-document limit under concurrency."""

import asyncio
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.contracts.documents import DocumentStatus, MaterialRole, PartDraft, SourceType
from src.app.contracts.documents.generation import GenerationAnswers
from src.app.exceptions.documents import ProcessingLimitError
from src.app.repositories.document_part_repository import DocumentPartRepository
from src.app.repositories.document_repository import DocumentRepository
from src.app.repositories.generation_ledger_repository import GenerationLedgerRepository
from src.app.repositories.user_material_repository import UserMaterialRepository
from src.app.repositories.user_repository import UserRepository
from src.app.services.documents.generation_service import GenerationService
from src.app.services.documents.splitting import TopicTreePlanner
from src.app.services.quota.ledger import QuotaLedger
from tests.support.fakes.tasks import FakeTaskDispatcher

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
            await documents.set_topic_tree(doc.id, {"topics": [{"id": "t", "title": "T", "children": []}]})
            await DocumentPartRepository(session).add_many(
                doc.id,
                [
                    PartDraft(index=0, title="T", topic_ids=["t"], source_markdown="text", token_count=1),
                ],
            )
            ids.append(doc.id)
    dispatcher = FakeTaskDispatcher()

    async def start(doc_id: UUID) -> bool:
        async with session_factory() as session:
            users = UserRepository(session)
            service = GenerationService(
                documents=DocumentRepository(session),
                materials=UserMaterialRepository(session),
                parts=DocumentPartRepository(session),
                planner=TopicTreePlanner(),
                ledger=QuotaLedger(users=users, ledger=GenerationLedgerRepository(session)),
                session=session,
                users=users,
                dispatcher=dispatcher,
            )
            try:
                await service.start(
                    user_id=user.id,
                    document_id=doc_id,
                    topic_ids=["t"],
                    answers=GenerationAnswers(level="novice", goal="exam", depth="standard"),
                )
            except ProcessingLimitError:
                return False
            return True

    results = await asyncio.gather(*(start(doc_id) for doc_id in ids))
    assert sorted(results) == [False, True, True]
    assert len(dispatcher.calls) == 2
    async with session_factory() as session:
        assert await DocumentRepository(session).count_active(user.id) == 2
