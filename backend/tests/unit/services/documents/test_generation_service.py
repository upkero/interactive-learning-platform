"""Unit tests 1.4.6: GenerationService.plan — pure preview, no writes."""

from datetime import date
from typing import cast
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.contracts.documents import DocumentStatus, MaterialRole, PartDraft, SourceType
from src.app.contracts.documents.generation import GenerationAnswers
from src.app.core.clock import Clock
from src.app.exceptions.documents import DocumentNotFoundError, DocumentNotReadyError
from src.app.exceptions.quota import QuotaExceededError
from src.app.services.documents.generation_service import GenerationService
from src.app.services.documents.splitting import TopicTreePlanner
from src.app.services.quota.ledger import QuotaLedger
from tests.support.fakes.repositories.documents import (
    FakeDocumentPartRepository,
    FakeDocumentRepository,
    FakeUserMaterialRepository,
)
from tests.support.fakes.repositories.quota import FakeGenerationLedgerRepository
from tests.support.fakes.repositories.users import FakeUserRepository
from tests.support.fakes.tasks import FakeTaskDispatcher

pytestmark = pytest.mark.unit

_TREE = {
    "topics": [
        {
            "id": "topic-adaptive",
            "title": "Adaptive learning",
            "children": [{"id": "topic-chunking", "title": "Semantic chunking", "children": []}],
        },
        {"id": "topic-quota", "title": "Quota and generation pipeline", "children": []},
    ]
}


class _FixedClock(Clock):
    def today(self) -> date:
        return date(2026, 11, 14)


def _service() -> tuple[
    GenerationService,
    FakeDocumentRepository,
    FakeUserMaterialRepository,
    FakeDocumentPartRepository,
    FakeGenerationLedgerRepository,
    FakeUserRepository,
]:
    documents = FakeDocumentRepository()
    materials = FakeUserMaterialRepository()
    parts = FakeDocumentPartRepository()
    ledger_repo = FakeGenerationLedgerRepository()
    users = FakeUserRepository()
    service = GenerationService(
        documents=documents,
        materials=materials,
        parts=parts,
        planner=TopicTreePlanner(),
        ledger=QuotaLedger(users=users, ledger=ledger_repo, clock=_FixedClock()),
    )
    return service, documents, materials, parts, ledger_repo, users


async def _parsed_document(
    users: FakeUserRepository,
    documents: FakeDocumentRepository,
    materials: FakeUserMaterialRepository,
    parts: FakeDocumentPartRepository,
) -> tuple[UUID, UUID]:
    owner_record = await users.create(email=f"u-{uuid4()}@example.com", password_hash="hash")
    owner = owner_record.id
    document = await documents.create(
        owner_id=owner,
        title="Introduction to adaptive learning",
        source_type=SourceType.UPLOAD,
        object_key="docs/demo/introduction.md",
        mime_type="text/markdown",
        size_bytes=4096,
        checksum="d" * 64,
    )
    await documents.set_status(document.id, DocumentStatus.PARSED)
    await documents.set_topic_tree(document.id, _TREE)
    await materials.create(user_id=owner, document_id=document.id, role=MaterialRole.OWNER)
    # seed parts like the dev seed does (142 + 178 + 96 tokens)
    await parts.add_many(
        document.id,
        [
            PartDraft(
                index=0,
                title="What adaptive learning is",
                topic_ids=["topic-adaptive", "topic-chunking"],
                source_markdown="part one",
                token_count=142,
                profile={},
            ),
            PartDraft(
                index=1,
                title="Topic tree and semantic chunks",
                topic_ids=["topic-chunking", "topic-tree"],
                source_markdown="part two",
                token_count=178,
                profile={},
            ),
            PartDraft(
                index=2,
                title="Quota and generation pipeline",
                topic_ids=["topic-quota"],
                source_markdown="part three",
                token_count=96,
                profile={},
            ),
        ],
    )
    return owner, document.id


async def test_plan_returns_preview_cost_and_available() -> None:
    service, documents, materials, parts, ledger_repo, users = _service()
    owner, document_id = await _parsed_document(users, documents, materials, parts)

    plan, available = await service.plan(
        user_id=owner,
        document_id=document_id,
        topic_ids=["topic-adaptive", "topic-quota"],
    )

    # adaptive: 142+178 (each part counted once per subtree); quota: 96.
    # The short quota part (< 5000) is glued to the previous one (1.10.1)
    assert [(p.index, p.tokens) for p in plan.parts] == [(0, 416)]
    assert plan.parts[0].title == "Adaptive learning, Quota and generation pipeline"
    assert len(plan.parts) == 1
    assert available == 20  # default monthly limit, nothing reserved

    # the plan is a pure read: the journal is untouched
    assert ledger_repo._entries == []


async def test_two_consecutive_calls_return_the_same_answer() -> None:
    service, documents, materials, parts, ledger_repo, users = _service()
    owner, document_id = await _parsed_document(users, documents, materials, parts)

    first = await service.plan(
        user_id=owner,
        document_id=document_id,
        topic_ids=["topic-adaptive"],
    )
    second = await service.plan(
        user_id=owner,
        document_id=document_id,
        topic_ids=["topic-adaptive"],
    )
    assert first == second
    assert ledger_repo._entries == []


async def test_shared_user_cannot_plan() -> None:
    service, documents, materials, parts, _ledger, users = _service()
    _owner, document_id = await _parsed_document(users, documents, materials, parts)
    stranger = uuid4()
    await materials.create(user_id=stranger, document_id=document_id, role=MaterialRole.SHARED)

    with pytest.raises(DocumentNotFoundError):
        await service.plan(user_id=stranger, document_id=document_id, topic_ids=["topic-adaptive"])


async def test_parsing_document_is_409() -> None:
    service, documents, materials, _parts, _ledger, _users = _service()
    owner = uuid4()
    document = await documents.create(
        owner_id=owner,
        title="t",
        source_type=SourceType.UPLOAD,
        object_key="docs/x.md",
        mime_type="text/markdown",
        size_bytes=1,
        checksum="d" * 64,
    )
    await documents.set_status(document.id, DocumentStatus.PARSING)
    await materials.create(user_id=owner, document_id=document.id, role=MaterialRole.OWNER)

    with pytest.raises(DocumentNotReadyError) as exc_info:
        await service.plan(user_id=owner, document_id=document.id, topic_ids=["a"])
    assert exc_info.value.extra == {"status": "parsing"}


async def test_start_reserves_and_dispatches_after_commit() -> None:
    _, documents, materials, parts, ledger_repo, users = _service()
    owner, document_id = await _parsed_document(users, documents, materials, parts)
    session = AsyncMock(spec=AsyncSession)

    class CommitCheckingDispatcher(FakeTaskDispatcher):
        async def enqueue_part(self, part_id: UUID, *, high: bool = False) -> None:
            session.commit.assert_awaited_once()
            await super().enqueue_part(part_id, high=high)

    dispatcher = CommitCheckingDispatcher()
    service = GenerationService(
        documents=documents,
        materials=materials,
        parts=parts,
        planner=TopicTreePlanner(),
        ledger=QuotaLedger(users=users, ledger=ledger_repo, clock=_FixedClock()),
        users=users,
        session=cast(AsyncSession, session),
        dispatcher=dispatcher,
    )
    started = await service.start(
        user_id=owner,
        document_id=document_id,
        topic_ids=["topic-adaptive"],
        answers=GenerationAnswers(level="novice", goal="exam", depth="standard"),
    )
    session.commit.assert_awaited_once()
    assert started.cost == 1
    assert started.available == 19
    assert dispatcher.calls == [("enqueue_part", (started.part_ids[0], True))]
    assert ledger_repo._entries[0].delta == -1
    part = await parts.get(started.part_ids[0])
    assert part is not None
    assert part.index == 3
    assert part.source_markdown == "part one\n\npart two"
    assert (await users.get(owner)).profile["last_answers"]["goal"] == "exam"  # type: ignore[union-attr]


async def test_start_rejects_insufficient_quota_without_writes() -> None:
    _, documents, materials, parts, ledger_repo, users = _service()
    owner, document_id = await _parsed_document(users, documents, materials, parts)
    from dataclasses import replace

    users._users[owner] = replace(users._users[owner], monthly_limit=0)
    session = AsyncMock(spec=AsyncSession)
    dispatcher = FakeTaskDispatcher()
    service = GenerationService(
        documents=documents,
        materials=materials,
        parts=parts,
        planner=TopicTreePlanner(),
        ledger=QuotaLedger(users=users, ledger=ledger_repo, clock=_FixedClock()),
        users=users,
        session=cast(AsyncSession, session),
        dispatcher=dispatcher,
    )
    with pytest.raises(QuotaExceededError) as error:
        await service.start(
            user_id=owner,
            document_id=document_id,
            topic_ids=["topic-adaptive"],
            answers=GenerationAnswers(level="novice", goal="exam", depth="standard"),
        )
    assert error.value.extra == {"available": 0, "requested": 1}
    assert len(await parts.list_by_document(document_id)) == 3
    assert ledger_repo._entries == []
    assert dispatcher.calls == []
    session.rollback.assert_awaited_once()
    session.commit.assert_not_awaited()


async def test_start_requires_owner_even_when_processing_limit_is_full() -> None:
    _, documents, materials, parts, ledger_repo, users = _service()
    owner, document_id = await _parsed_document(users, documents, materials, parts)
    stranger = await users.create(email="stranger@example.com", password_hash="hash")
    await materials.create(user_id=stranger.id, document_id=document_id, role=MaterialRole.SHARED)
    for _ in range(2):
        await documents.create(
            owner_id=stranger.id,
            title="busy",
            source_type=SourceType.UPLOAD,
            object_key="file",
            mime_type="text/markdown",
            size_bytes=1,
            checksum="a" * 64,
        )
    session = AsyncMock(spec=AsyncSession)
    service = GenerationService(
        documents=documents,
        materials=materials,
        parts=parts,
        planner=TopicTreePlanner(),
        ledger=QuotaLedger(users=users, ledger=ledger_repo, clock=_FixedClock()),
        users=users,
        session=cast(AsyncSession, session),
        dispatcher=FakeTaskDispatcher(),
    )
    with pytest.raises(DocumentNotFoundError):
        await service.start(
            user_id=stranger.id,
            document_id=document_id,
            topic_ids=["topic-adaptive"],
            answers=GenerationAnswers(level="novice", goal="exam", depth="standard"),
        )
    assert (await documents.get(document_id)).owner_id == owner  # type: ignore[union-attr]
    assert ledger_repo._entries == []
