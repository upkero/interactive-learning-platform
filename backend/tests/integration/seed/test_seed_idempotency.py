"""Demo data are idempotent and usable by the real HTTP generation flow."""

from typing import cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.bootstrap.container import ApplicationContainer
from src.app.contracts.documents.statuses import DocumentStatus, PartStatus
from src.app.contracts.quota import LedgerOp
from src.app.core.settings.quota import QuotaSettings
from src.app.exceptions.quota import QuotaExceededError
from src.app.models.document import Document
from src.app.models.document_part import DocumentPart
from src.app.models.generation_ledger import GenerationLedger
from src.app.models.primitive import Primitive
from src.app.models.user import User
from src.app.seed import dev_seed
from src.app.seed.dev_seed import ALICE_EMAIL, BOB_EMAIL, seed_dev
from src.app.services.quota.quota_ledger import QuotaLedger
from src.app.storage.object_keys import image_key, parsed_markdown_key, source_key
from src.main import create_app
from tests.support.fakes.services.task_dispatcher import FakeTaskDispatcher
from tests.support.fakes.storage.object_storage_client import FakeObjectStorageClient
from tests.support.types import SessionFactory

pytestmark = pytest.mark.integration


async def test_seed_is_idempotent_and_has_no_orphan_queued_parts(
    session_factory: SessionFactory, ledger: QuotaLedger
) -> None:
    storage = FakeObjectStorageClient()
    first = await seed_dev(
        session_factory, password="seed-test-password", ledger=ledger, storage=storage, fake_embeddings=True
    )
    second = await seed_dev(
        session_factory, password="seed-test-password", ledger=ledger, storage=storage, fake_embeddings=True
    )
    assert first.startswith("seeded") and second == "already seeded"
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(User)) == 2
        documents = (await session.scalars(select(Document))).all()
        assert len(documents) == 2
        parts = (await session.scalars(select(DocumentPart))).all()
        assert len(parts) == 1 and parts[0].status == PartStatus.PUBLISHED.value
        assert parts[0].document_id == next(d.id for d in documents if d.status == DocumentStatus.DONE.value)
        assert [(e.op, e.delta) for e in (await session.scalars(select(GenerationLedger))).all()] == [
            (LedgerOp.RESERVE.value, -1),
            (LedgerOp.CHARGE.value, 0),
        ]


async def test_seed_storage_failure_rolls_back_database(session_factory: SessionFactory, ledger: QuotaLedger) -> None:
    storage = FakeObjectStorageClient(error=RuntimeError("storage unavailable"))
    with pytest.raises(RuntimeError, match="storage unavailable"):
        await seed_dev(session_factory, password="seed-test-password", ledger=ledger, storage=storage)
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(User)) == 0


async def test_seed_quota_failure_rolls_back_all_demo_data(
    session_factory: SessionFactory, monkeypatch: pytest.MonkeyPatch, ledger: QuotaLedger
) -> None:
    monkeypatch.setattr(dev_seed, "get_quota_settings", lambda: QuotaSettings(default_monthly_limit=0))
    with pytest.raises(QuotaExceededError):
        await seed_dev(
            session_factory,
            password="seed-test-password",
            ledger=ledger,
            storage=FakeObjectStorageClient(),
            fake_embeddings=True,
        )
    async with session_factory() as session:
        for model in (User, Document, DocumentPart, GenerationLedger, Primitive):
            assert await session.scalar(select(func.count()).select_from(model)) == 0


async def test_seed_can_login_plan_and_generate_with_real_s3(
    session_factory: async_sessionmaker[AsyncSession], container: ApplicationContainer, ledger: QuotaLedger
) -> None:
    await seed_dev(
        session_factory,
        password="seed-test-password",
        ledger=ledger,
        storage=container.object_storage,
        fake_embeddings=True,
    )
    async with session_factory() as session:
        document = (await session.scalars(select(Document).where(Document.status == DocumentStatus.PARSED.value))).one()
        done = (await session.scalars(select(Document).where(Document.status == DocumentStatus.DONE.value))).one()
    for seeded in (document, done):
        assert seeded.object_key == source_key(seeded.owner_id, seeded.id, "md")
        source = await container.object_storage.get_object(bucket="documents", key=seeded.object_key)
        parsed = await container.object_storage.get_object(
            bucket="documents", key=parsed_markdown_key(seeded.owner_id, seeded.id)
        )
        assert source == parsed and len(parsed) >= 1600
    image = await container.object_storage.get_object(bucket="images", key=image_key(done.id, 1))
    assert image.startswith(b"\x89PNG\r\n\x1a\n")
    with TestClient(create_app()) as client:
        app_container = cast(ApplicationContainer, cast(FastAPI, client.app).state.container)
        app_container.__dict__["task_dispatcher"] = FakeTaskDispatcher()
        for email in (ALICE_EMAIL, BOB_EMAIL):
            response = client.post("/api/v1/auth/login", json={"email": email, "password": "seed-test-password"})
            assert response.status_code == 200, response.text
            if email == ALICE_EMAIL:
                preview = client.post(f"/api/v1/documents/{document.id}/plan", json={"topic_ids": ["topic-adaptive"]})
                assert preview.status_code == 200, preview.text
                generated = client.post(
                    f"/api/v1/documents/{document.id}/generate",
                    json={
                        "topic_ids": ["topic-adaptive"],
                        "answers": {"level": "novice", "goal": "exam", "depth": "standard"},
                    },
                )
                assert generated.status_code == 202, generated.text
