import json
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.contracts.documents.statuses import PartStatus
from src.app.contracts.quota import LedgerOp
from src.app.services.solver.pipeline import stub_pipeline as stub_pipeline_module
from src.app.services.solver.pipeline.stub_pipeline import StubPipeline
from tests.support.fakes.db.session import FakeSession
from tests.support.fakes.notifications.service import FakeDocumentNotifications
from tests.support.fakes.observability.metrics_collector import RecordingMetricsCollector
from tests.support.fakes.repositories.users import FakeUserRepository
from tests.support.fakes.services.progress_notifier import FakeProgressNotifier
from tests.support.fixtures.solver import build_recovery

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_stub_publishes_once_and_duplicate_delivery_is_noop() -> None:
    case = await build_recovery(PartStatus.QUEUED, 0)
    part = case.part
    session = FakeSession()
    notifier = FakeProgressNotifier()
    notifications = FakeDocumentNotifications()
    metrics = RecordingMetricsCollector()
    pipeline = StubPipeline(
        session_factory=cast(async_sessionmaker[AsyncSession], lambda: session),
        parts=lambda _: case.parts,
        documents=lambda _: case.documents,
        ledger=case.quota,
        notifier=notifier,
        users=lambda _: FakeUserRepository(),
        notifications=notifications,
        metrics=metrics,
        delay=0,
    )
    await pipeline.process(part.id)
    await pipeline.process(part.id)
    result = await case.parts.get(part.id)
    assert result is not None and result.status is PartStatus.PUBLISHED
    assert result.attempts == 1 and result.content is not None
    assert result.content["schema_version"] == 1
    assert [entry.op for entry in case.ledger.entries] == [LedgerOp.RESERVE, LedgerOp.CHARGE]
    assert [event[1] for event in notifier.events] == ["part_status"] * 4 + ["part_ready", "document_done"]
    assert notifications.completed == [part.document_id]
    observations = metrics.histograms_named("part.processing_duration_seconds")
    assert len(observations) == 1 and observations[0].labels == {"outcome": "published"}


async def test_stub_does_not_notify_before_all_parts_finish() -> None:
    case = await build_recovery(PartStatus.QUEUED, 0)
    extra = await case.parts.add_many(
        case.document.id,
        [
            replace(
                case.parts.drafts[case.part.id],
                index=1,
            )
        ],
    )
    assert len(extra) == 1
    notifications = FakeDocumentNotifications()
    pipeline = StubPipeline(
        session_factory=cast(async_sessionmaker[AsyncSession], lambda: FakeSession()),
        parts=lambda _: case.parts,
        documents=lambda _: case.documents,
        ledger=case.quota,
        notifier=FakeProgressNotifier(),
        users=lambda _: FakeUserRepository(),
        notifications=notifications,
        delay=0,
    )
    await pipeline.process(case.part.id)
    assert notifications.completed == []


async def test_metrics_failure_does_not_interrupt_published_events(caplog: pytest.LogCaptureFixture) -> None:
    class BrokenMetrics(RecordingMetricsCollector):
        def observe_histogram(
            self,
            name: str,
            value: float,
            *,
            labels: Mapping[str, str] | None = None,
            buckets: tuple[float, ...] | None = None,
        ) -> None:
            raise OSError("metrics unavailable")

    case = await build_recovery(PartStatus.QUEUED, 0)
    notifier = FakeProgressNotifier()
    notifications = FakeDocumentNotifications()
    pipeline = StubPipeline(
        session_factory=cast(async_sessionmaker[AsyncSession], lambda: FakeSession()),
        parts=lambda _: case.parts,
        documents=lambda _: case.documents,
        ledger=case.quota,
        notifier=notifier,
        users=lambda _: FakeUserRepository(),
        notifications=notifications,
        metrics=BrokenMetrics(),
        delay=0,
    )
    with caplog.at_level("INFO", logger="grasp.decisions"):
        await pipeline.process(case.part.id)
        await pipeline.process(case.part.id)
    assert [entry.op for entry in case.ledger.entries] == [LedgerOp.RESERVE, LedgerOp.CHARGE]
    assert [e[1] for e in notifier.events] == ["part_status"] * 4 + ["part_ready", "document_done"]
    assert notifications.completed == [case.part.document_id]
    assert len([r for r in caplog.records if r.__dict__.get("event") == "part.summary"]) == 1


async def test_invalid_fixture_fails_before_publishing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fixture = tmp_path / "published.json"
    fixture.write_text(json.dumps({"content": {"schema_version": 2}}), encoding="utf-8")
    monkeypatch.setattr(stub_pipeline_module, "PUBLISHED_PART_FIXTURE", fixture)
    times = iter((10.0, 13.0))
    monkeypatch.setattr(stub_pipeline_module, "perf_counter", lambda: next(times))
    case = await build_recovery(PartStatus.QUEUED, 0)
    metrics = RecordingMetricsCollector()
    pipeline = StubPipeline(
        session_factory=cast(async_sessionmaker[AsyncSession], lambda: FakeSession()),
        parts=lambda _: case.parts,
        documents=lambda _: case.documents,
        ledger=case.quota,
        notifier=case.notifier,
        users=lambda _: FakeUserRepository(),
        notifications=FakeDocumentNotifications(),
        metrics=metrics,
        delay=0,
    )
    with pytest.raises(RuntimeError, match="Invalid published part fixture"):
        await pipeline.process(case.part.id)
    part = await case.parts.get(case.part.id)
    assert part is not None and part.status is PartStatus.MAIN_PASS and part.content is None
    assert case.notifier.events == []
    observations = metrics.histograms_named("part.processing_duration_seconds")
    assert len(observations) == 1
    assert observations[0].labels == {"outcome": "failed"}
    assert observations[0].value == 3.0


async def test_locale_read_error_after_acceptance_is_recorded() -> None:
    class BrokenUsers(FakeUserRepository):
        async def get_locale_by_document(self, document_id: UUID) -> str:
            raise RuntimeError("locale unavailable")

    case = await build_recovery(PartStatus.QUEUED, 0)
    metrics = RecordingMetricsCollector()
    pipeline = StubPipeline(
        session_factory=cast(async_sessionmaker[AsyncSession], lambda: FakeSession()),
        parts=lambda _: case.parts,
        documents=lambda _: case.documents,
        ledger=case.quota,
        notifier=case.notifier,
        users=lambda _: BrokenUsers(),
        notifications=FakeDocumentNotifications(),
        metrics=metrics,
        delay=0,
    )
    with pytest.raises(RuntimeError, match="locale unavailable"):
        await pipeline.process(case.part.id)
    observations = metrics.histograms_named("part.processing_duration_seconds")
    assert len(observations) == 1 and observations[0].labels == {"outcome": "failed"}


async def test_pipeline_messages_use_owner_locale_and_part_number() -> None:
    case = await build_recovery(PartStatus.QUEUED, 0)
    users = FakeUserRepository()
    # A decoy user makes a fake that returns "the first user" fail this test:
    # the locale must come from the owner of this particular document.
    await users.create(email="decoy@example.com", password_hash="hash", locale="ru")
    user = await users.create(email="en@example.com", password_hash="hash", locale="en")
    users._users[case.document.owner_id] = replace(user, id=case.document.owner_id)
    users.attach_document(case.document.id, case.document.owner_id)
    notifier = FakeProgressNotifier()
    pipeline = StubPipeline(
        session_factory=cast(async_sessionmaker[AsyncSession], lambda: FakeSession()),
        parts=lambda _: case.parts,
        documents=lambda _: case.documents,
        ledger=case.quota,
        notifier=notifier,
        users=lambda _: users,
        notifications=FakeDocumentNotifications(),
        delay=0,
    )
    await pipeline.process(case.part.id)
    messages = [event[4] for event in notifier.events]
    assert all(message and "{" not in message for message in messages)
    assert "Analyzing part 1" in messages
    assert "Your material is ready" in messages


async def test_pipeline_uses_run_relative_part_number_after_previous_run() -> None:
    case = await build_recovery(PartStatus.QUEUED, 0)
    await case.documents.set_generation_start(case.document.id, 4)
    part = replace(case.part, index=4)
    case.parts.store_record(part)
    users = FakeUserRepository()
    owner = await users.create(email="owner@example.com", password_hash="hash", locale="en")
    users._users[case.document.owner_id] = replace(owner, id=case.document.owner_id)
    users.attach_document(case.document.id, case.document.owner_id)
    notifier = FakeProgressNotifier()
    pipeline = StubPipeline(
        session_factory=cast(async_sessionmaker[AsyncSession], lambda: FakeSession()),
        parts=lambda _: case.parts,
        documents=lambda _: case.documents,
        ledger=case.quota,
        notifier=notifier,
        users=lambda _: users,
        notifications=FakeDocumentNotifications(),
        delay=0,
    )
    await pipeline.process(part.id)
    assert "Analyzing part 1" in [event[4] for event in notifier.events]
