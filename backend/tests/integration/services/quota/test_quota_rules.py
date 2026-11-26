"""Quota spending through generation, publication and recovery."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.api.v1.middleware.rate_limit import limiter
from src.app.bootstrap.container import ApplicationContainer
from src.app.contracts.documents import DocumentStatus, MaterialRole, PartDraft, PartStatus, SourceType
from src.app.contracts.quota import LedgerOp
from src.app.contracts.widgets import UsageStatus, WidgetKind, WidgetUsageDraft
from src.app.models.document_part import DocumentPart
from src.app.models.generation_ledger import GenerationLedger
from src.app.repositories.document_part_repository import DocumentPartRepository
from src.app.repositories.document_repository import DocumentRepository
from src.app.repositories.user_material_repository import UserMaterialRepository
from src.app.repositories.user_repository import UserRepository
from src.app.repositories.widget_repository import WidgetRepository
from src.app.repositories.widget_usage_repository import WidgetUsageRepository
from src.app.services.sharing.sharing_service import SharingService
from src.app.services.solver.pipeline.stub_pipeline import StubPipeline
from src.app.services.solver.pipeline.watchdog import Watchdog
from src.app.storage.object_keys import parsed_markdown_key
from src.main import create_app
from tests.support.fakes.services.progress_notifier import FakeProgressNotifier
from tests.support.fakes.services.task_dispatcher import FakeTaskDispatcher
from tests.support.fakes.storage.object_storage_client import FakeObjectStorageClient
from tests.support.fixtures.documents import topic_node

pytestmark = pytest.mark.integration


@pytest.fixture
def client() -> Iterator[TestClient]:
    limiter.reset()
    with TestClient(create_app(), raise_server_exceptions=False) as client:
        container = cast(ApplicationContainer, cast(FastAPI, client.app).state.container)
        container.__dict__["object_storage"] = FakeObjectStorageClient()
        container.__dict__["task_dispatcher"] = FakeTaskDispatcher()
        yield client


async def _prepare_parsed_document(
    user_id: UUID, session_factory: async_sessionmaker[AsyncSession], container: ApplicationContainer
) -> UUID:
    async with session_factory() as session, session.begin():
        documents = DocumentRepository(session)
        document = await documents.create(
            owner_id=user_id,
            title="Quota",
            source_type=SourceType.UPLOAD,
            object_key="quota.md",
            mime_type="text/markdown",
            size_bytes=3,
            checksum="c" * 64,
        )
        await UserMaterialRepository(session).create(user_id=user_id, document_id=document.id, role=MaterialRole.OWNER)
        await documents.set_status(document.id, DocumentStatus.PARSED)
        chapter_size = 16_000
        await documents.set_topic_tree(
            document.id,
            [topic_node(str(i), f"Topic {i}", i * chapter_size, (i + 1) * chapter_size, 20) for i in range(3)],
        )
    await container.object_storage.put_object(
        bucket="documents",
        key=parsed_markdown_key(user_id, document.id),
        data=b"a " * (chapter_size * 3 // 2),
        content_type="text/markdown",
    )
    return document.id


async def test_generate_publish_and_watchdog_refund(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession], watchdog: Watchdog
) -> None:
    response = client.post(
        "/api/v1/auth/register", json={"email": "quota-e2e@example.com", "password": "long-enough-password"}
    )
    assert response.status_code == 201, response.text
    user_id = UUID(response.json()["id"])
    container = cast(ApplicationContainer, cast(FastAPI, client.app).state.container)
    document_id = await _prepare_parsed_document(user_id, session_factory, container)
    quota_response = client.get("/api/v1/me/quota").json()
    quota_before = quota_response["available"]
    assert quota_before == quota_response["monthly_limit"]
    plan = client.post(f"/api/v1/documents/{document_id}/plan", json={"topic_ids": ["0", "1", "2"]})
    assert plan.status_code == 200 and plan.json()["cost"] == 3, plan.text
    assert client.get("/api/v1/me/quota").json()["available"] == quota_before
    response = client.post(
        f"/api/v1/documents/{document_id}/generate",
        json={"topic_ids": ["0", "1", "2"], "answers": {"level": "novice", "goal": "exam", "depth": "standard"}},
    )
    assert response.status_code == 202, response.text
    part_ids = [UUID(value) for value in response.json()["part_ids"]]
    assert len(part_ids) == 3
    notifier = FakeProgressNotifier()
    pipeline = StubPipeline(
        session_factory=session_factory,
        parts=DocumentPartRepository,
        documents=DocumentRepository,
        ledger=container.quota_ledger,
        notifier=notifier,
        users=UserRepository,
        notifications=container.notification_service,
        delay=0,
    )
    await pipeline.process(part_ids[0])
    await pipeline.process(part_ids[1])
    async with session_factory() as session, session.begin():
        parts = DocumentPartRepository(session)
        await parts.transition(part_ids[2], frozenset({PartStatus.QUEUED}), PartStatus.MAIN_PASS, bump_attempts=True)
        await parts.transition(part_ids[2], frozenset({PartStatus.MAIN_PASS}), PartStatus.QUEUED)
        await parts.transition(part_ids[2], frozenset({PartStatus.QUEUED}), PartStatus.MAIN_PASS, bump_attempts=True)
        await session.execute(
            update(DocumentPart)
            .where(DocumentPart.id == part_ids[2])
            .values(stage_changed_at=datetime.now(UTC) - timedelta(minutes=11))
        )
    assert (await watchdog.tick()).failed == 1
    assert client.get("/api/v1/me/quota").json()["available"] == quota_before - 2
    async with session_factory() as session:
        entries = (await session.scalars(select(GenerationLedger).order_by(GenerationLedger.id))).all()
        saved_periods = (
            await session.scalars(
                select(DocumentPart.quota_period_start).where(DocumentPart.document_id == document_id)
            )
        ).all()
        assert saved_periods == [entries[0].period_start] * 3
        assert [(entry.op, entry.delta) for entry in entries] == [
            (LedgerOp.RESERVE.value, -3),
            (LedgerOp.CHARGE.value, 0),
            (LedgerOp.CHARGE.value, 0),
            (LedgerOp.REFUND.value, 1),
        ]


async def test_watchdog_retry_does_not_spend_again(
    session_factory: async_sessionmaker[AsyncSession],
    part_ids: tuple[UUID, UUID, UUID],
    container: ApplicationContainer,
    watchdog: Watchdog,
) -> None:
    user_id, document_id, part_id = part_ids
    async with session_factory() as session, session.begin():
        await container.quota_ledger.reserve(session, user_id=user_id, document_id=document_id, parts=1)
        await DocumentPartRepository(session).transition(
            part_id, frozenset({PartStatus.QUEUED}), PartStatus.MAIN_PASS, bump_attempts=True
        )
        await session.execute(
            update(DocumentPart)
            .where(DocumentPart.id == part_id)
            .values(stage_changed_at=datetime.now(UTC) - timedelta(minutes=11))
        )
    assert (await watchdog.tick()).requeued == 1
    async with session_factory() as session:
        assert (await container.quota_ledger.available(session, user_id=user_id)).available == 19
        entries = (await session.scalars(select(GenerationLedger))).all()
        assert [(entry.op, entry.delta) for entry in entries] == [(LedgerOp.RESERVE.value, -1)]


async def test_receiving_shared_material_does_not_spend_quota(
    session_factory: async_sessionmaker[AsyncSession],
    part_ids: tuple[UUID, UUID, UUID],
    container: ApplicationContainer,
) -> None:
    owner_id, document_id, _ = part_ids
    async with session_factory() as session, session.begin():
        recipient = await UserRepository(session).create(
            email="recipient@example.com", password_hash="hash", monthly_limit=20
        )
        await UserMaterialRepository(session).create(user_id=owner_id, document_id=document_id, role=MaterialRole.OWNER)
    sharing = SharingService(session_factory=session_factory, materials=UserMaterialRepository, users=UserRepository)
    await sharing.share(owner_id=owner_id, document_id=document_id, email=recipient.email)
    async with session_factory() as session:
        assert (await container.quota_ledger.available(session, user_id=recipient.id)).available == 20
        assert (await container.quota_ledger.available(session, user_id=owner_id)).available == 20
        assert (await session.scalars(select(GenerationLedger))).all() == []


async def test_upload_browse_quiz_and_report_do_not_spend(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    registered = client.post(
        "/api/v1/auth/register", json={"email": "quota-reads@example.com", "password": "long-enough-password"}
    )
    assert registered.status_code == 201, registered.text
    uploaded = client.post("/api/v1/documents", files={"file": ("notes.md", b"# Notes\nContent", "text/markdown")})
    assert uploaded.status_code == 201, uploaded.text
    document_id = UUID(uploaded.json()["id"])
    assert client.get("/api/v1/me/quota").json()["available"] == 20
    async with session_factory() as session, session.begin():
        documents = DocumentRepository(session)
        await documents.set_status(document_id, DocumentStatus.PARSED)
        await documents.set_topic_tree(
            document_id,
            [topic_node("t", "Notes", 0, 15, 2)],
        )
        (part,) = await DocumentPartRepository(session).add_many(
            document_id,
            [
                PartDraft(
                    index=0,
                    title="Notes",
                    topic_ids=["t"],
                    source_markdown="text",
                    token_count=2,
                    quota_period_start=None,
                )
            ],
        )
        await session.execute(
            update(DocumentPart)
            .where(DocumentPart.id == part.id)
            .values(
                status=PartStatus.PUBLISHED.value,
                content={
                    "title": "Notes",
                    "markdown": "text",
                    "quizzes": [{"key": "q", "type": "single_choice"}],
                    "answer_keys": {"q": {"correct_id": "a", "explanation": "yes"}},
                },
            )
        )
        widget = await WidgetRepository(session).create(kind=WidgetKind.CODE, source_tsx="x", compiled_js="x")
        await WidgetUsageRepository(session).add_many(
            part.id,
            [
                WidgetUsageDraft(
                    widget_id=widget.id,
                    directive_ref="slot",
                    position=0,
                    params=None,
                    status=UsageStatus.READY,
                )
            ],
        )
    for path in (f"/api/v1/documents/{document_id}", f"/api/v1/documents/{document_id}/topics"):
        response = client.get(path)
        assert response.status_code == 200, response.text
    answer = client.post("/api/v1/quiz-attempts", json={"part_id": str(part.id), "quiz_key": "q", "answer": "a"})
    assert answer.status_code == 200, answer.text
    report = client.post(f"/api/v1/widgets/{widget.id}/reports", json={"part_id": str(part.id), "reason": "ugly"})
    assert report.status_code == 200, report.text
    assert client.get("/api/v1/me/quota").json()["available"] == 20
    async with session_factory() as session:
        assert (await session.scalars(select(GenerationLedger))).all() == []
