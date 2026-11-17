"""Integration test 1.2.8: ``seed-dev`` is idempotent and shapes demo data.

Runs the full ``seed_dev`` twice against real Postgres: the first run
inserts the demo dataset, the second one must be a no-op returning
``"already seeded"`` without duplicating rows.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select, update

from src.app.contracts.documents.statuses import DocumentStatus, PartStatus, SourceType
from src.app.contracts.quota import LedgerOp
from src.app.core.settings.quota import QuotaSettings
from src.app.exceptions.quota import QuotaExceededError
from src.app.models.document import Document
from src.app.models.document_part import DocumentPart
from src.app.models.generation_ledger import GenerationLedger
from src.app.models.primitive import Primitive
from src.app.models.user import User
from src.app.models.widget import Widget
from src.app.repositories.document_part_repository import DocumentPartRepository
from src.app.repositories.document_repository import DocumentRepository
from src.app.seed import dev_seed
from src.app.seed.dev_seed import ALICE_EMAIL, BOB_EMAIL, seed_dev
from src.app.services.quota.quota_ledger import QuotaLedger
from src.app.services.solver.pipeline.stub_pipeline import StubPipeline
from src.app.services.solver.pipeline.watchdog import Watchdog
from tests.support.fakes.services.progress_notifier import FakeProgressNotifier
from tests.support.types import SessionFactory

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("monthly_limit", [20, 50])
async def test_seed_dev_is_idempotent(
    session_factory: SessionFactory, monkeypatch: pytest.MonkeyPatch, ledger: QuotaLedger, monthly_limit: int
) -> None:
    """Second seed run is a no-op; the demo dataset stays intact."""
    async with session_factory() as session:
        assert (await session.scalar(select(func.count()).select_from(User))) == 0

    monkeypatch.setattr(dev_seed, "get_quota_settings", lambda: QuotaSettings(default_monthly_limit=monthly_limit))
    first = await seed_dev(session_factory, password="seed-test-password", ledger=ledger, fake_embeddings=True)
    second = await seed_dev(session_factory, password="seed-test-password", ledger=ledger, fake_embeddings=True)

    assert first.startswith("seeded")
    assert second == "already seeded"

    async with session_factory() as session:
        user_count = await session.scalar(select(func.count()).select_from(User))
        assert user_count == 2
        users = (await session.scalars(select(User))).all()
        assert [user.monthly_limit for user in users] == [monthly_limit, monthly_limit]
        parts = (await session.scalars(select(DocumentPart))).all()
        assert len(parts) == 4 and all(part.quota_period_start is not None for part in parts)
        entries = (await session.scalars(select(GenerationLedger).order_by(GenerationLedger.id))).all()
        assert [(entry.op, entry.delta) for entry in entries] == [
            (LedgerOp.RESERVE.value, -3),
            (LedgerOp.RESERVE.value, -1),
            (LedgerOp.CHARGE.value, 0),
        ]
        assert entries[2].part_id in {part.id for part in parts if part.status == PartStatus.PUBLISHED.value}
        widget_count = await session.scalar(select(func.count()).select_from(Widget))
        assert widget_count is not None and widget_count > 0

        documents = (await session.scalars(select(Document).order_by(Document.title))).all()
        assert len(documents) == 2
        for user in users:
            owned_documents = {document.id for document in documents if document.owner_id == user.id}
            owned_parts = [part for part in parts if part.document_id in owned_documents]
            state = await ledger.available(session, user_id=user.id)
            assert state.available == monthly_limit - len(owned_parts)
            assert {part.quota_period_start for part in owned_parts} == {state.period.start}
            assert sum(entry.delta for entry in entries if entry.user_id == user.id) == -len(owned_parts)
        by_status = {doc.status: doc for doc in documents}
        assert set(by_status) == {DocumentStatus.PARSED.value, DocumentStatus.DONE.value}

        # Screen E1: parsed document carries a topic tree.
        parsed = by_status[DocumentStatus.PARSED.value]
        owner = await session.scalar(select(User.email).where(User.id == parsed.owner_id))
        assert owner == ALICE_EMAIL
        assert isinstance(parsed.topic_tree, list) and parsed.topic_tree
        assert parsed.source_type == SourceType.UPLOAD.value
        # Screen E6: done document holds exactly one published part with content.
        done = by_status[DocumentStatus.DONE.value]
        done_owner = await session.scalar(select(User.email).where(User.id == done.owner_id))
        assert done_owner == BOB_EMAIL
        assert done.source_type == SourceType.GDOCS.value and done.source_uri is not None
        assert isinstance(done.topic_tree, list) and done.topic_tree
        part = (
            await session.scalars(
                select(DocumentPart).where(
                    DocumentPart.document_id == done.id, DocumentPart.status == PartStatus.PUBLISHED.value
                )
            )
        ).one()
        assert part.content is not None and "markdown" in part.content
        assert part.published_at is not None


async def test_seeded_parts_can_publish_and_watchdog_can_refund(
    session_factory: SessionFactory, ledger: QuotaLedger, watchdog: Watchdog
) -> None:
    await seed_dev(session_factory, password="seed-test-password", ledger=ledger, fake_embeddings=True)
    async with session_factory() as session:
        alice = (await session.scalars(select(User).where(User.email == ALICE_EMAIL))).one()
        bob = (await session.scalars(select(User).where(User.email == BOB_EMAIL))).one()
        parts = (
            await session.scalars(
                select(DocumentPart).where(DocumentPart.status == PartStatus.QUEUED.value).order_by(DocumentPart.index)
            )
        ).all()
    assert len(parts) == 3
    pipeline = StubPipeline(
        session_factory=session_factory,
        parts=DocumentPartRepository,
        documents=DocumentRepository,
        ledger=ledger,
        notifier=FakeProgressNotifier(),
        delay=0,
    )
    for part in parts[:2]:
        await pipeline.process(part.id)
        # Re-delivery must not publish again or append another charge.
        await pipeline.process(part.id)
    async with session_factory() as session, session.begin():
        repository = DocumentPartRepository(session)
        for _ in range(2):
            await repository.transition(
                parts[2].id, frozenset({PartStatus.QUEUED}), PartStatus.MAIN_PASS, bump_attempts=True
            )
            await repository.transition(parts[2].id, frozenset({PartStatus.MAIN_PASS}), PartStatus.QUEUED)
        await repository.transition(parts[2].id, frozenset({PartStatus.QUEUED}), PartStatus.MAIN_PASS)
        await session.execute(
            update(DocumentPart)
            .where(DocumentPart.id == parts[2].id)
            .values(stage_changed_at=datetime.now(UTC) - timedelta(minutes=11))
        )
    assert (await watchdog.tick()).failed == 1
    assert (await watchdog.tick()).failed == 0
    async with session_factory() as session:
        assert (await ledger.available(session, user_id=alice.id)).available == alice.monthly_limit - 2
        assert (await ledger.available(session, user_id=bob.id)).available == bob.monthly_limit - 1
        saved = (await session.scalars(select(DocumentPart))).all()
        assert sum(part.status == PartStatus.PUBLISHED.value for part in saved) == 3
        assert sum(part.status == PartStatus.FAILED.value for part in saved) == 1
        entries = (await session.scalars(select(GenerationLedger))).all()
        assert sum(entry.op == LedgerOp.CHARGE.value for entry in entries) == 3
        assert sum(entry.op == LedgerOp.REFUND.value for entry in entries) == 1


async def test_seed_quota_failure_rolls_back_all_demo_data(
    session_factory: SessionFactory, monkeypatch: pytest.MonkeyPatch, ledger: QuotaLedger
) -> None:
    monkeypatch.setattr(dev_seed, "get_quota_settings", lambda: QuotaSettings(default_monthly_limit=2))
    with pytest.raises(QuotaExceededError):
        await seed_dev(session_factory, password="seed-test-password", ledger=ledger, fake_embeddings=True)
    async with session_factory() as session:
        for model in (User, Document, DocumentPart, GenerationLedger, Primitive):
            assert await session.scalar(select(func.count()).select_from(model)) == 0
