from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.contracts.documents.statuses import PartStatus
from src.app.contracts.progress import ProgressEventType
from src.app.contracts.quota import LedgerOp
from src.app.services.solver.pipeline.watchdog import Watchdog
from tests.support.fakes.db.session import FakeSession
from tests.support.fakes.observability.metrics_collector import RecordingMetricsCollector
from tests.support.fixtures.solver import RecoveryFixture, build_recovery

pytestmark = pytest.mark.unit


def watchdog_for(case: RecoveryFixture) -> tuple[Watchdog, RecordingMetricsCollector]:
    metrics = RecordingMetricsCollector()
    watchdog = Watchdog(
        session_factory=cast(async_sessionmaker[AsyncSession], lambda: FakeSession()),
        parts=lambda _: case.parts,
        documents=lambda _: case.documents,
        recovery=case.recovery,
        dispatcher=case.dispatcher,
        metrics=metrics,
    )
    return watchdog, metrics


def age(case: RecoveryFixture, minutes: int) -> None:
    case.parts.store_record(replace(case.part, stage_changed_at=datetime.now(UTC) - timedelta(minutes=minutes)))


async def test_watchdog_requeues_first_attempt() -> None:
    case = await build_recovery(PartStatus.MAIN_PASS, 1)
    age(case, 11)
    watchdog, metrics = watchdog_for(case)
    report = await watchdog.tick()
    assert report.requeued == 1 and report.failed == 0
    assert case.dispatcher.calls == [("enqueue_part", (case.part.id, False))]
    assert ("watchdog_actions_total", {"action": "requeued"}, 1) in metrics.labeled_counters
    assert [(e[1], e[3]) for e in case.notifier.events] == [(ProgressEventType.PART_STATUS, PartStatus.QUEUED.value)]


async def test_watchdog_fails_and_refunds_exhausted_attempt() -> None:
    case = await build_recovery(PartStatus.ASSEMBLING, 2)
    age(case, 11)
    watchdog, metrics = watchdog_for(case)
    assert (await watchdog.tick()).failed == 1
    assert [e.op for e in case.ledger.entries] == [LedgerOp.RESERVE, LedgerOp.REFUND]
    assert case.documents.refreshed == [case.part.document_id]
    assert ("watchdog_actions_total", {"action": "failed"}, 1) in metrics.labeled_counters
    assert [(e[1], e[3]) for e in case.notifier.events] == [
        (ProgressEventType.PART_STATUS, PartStatus.FAILED.value),
        (ProgressEventType.DOCUMENT_DONE, None),
    ]


async def test_watchdog_requeues_only_lost_queued_parts() -> None:
    case = await build_recovery(PartStatus.QUEUED, 0)
    watchdog, metrics = watchdog_for(case)
    age(case, 11)
    assert (await watchdog.tick()).lost == 0 and case.dispatcher.calls == []
    age(case, 31)
    assert (await watchdog.tick()).lost == 1
    part = await case.parts.get(case.part.id)
    assert part is not None and part.attempts == 0
    assert case.dispatcher.calls == [("enqueue_part", (case.part.id, False))]
    assert ("watchdog_actions_total", {"action": "lost"}, 1) in metrics.labeled_counters


async def test_watchdog_ignores_published_part() -> None:
    case = await build_recovery(PartStatus.PUBLISHED, 1)
    age(case, 31)
    watchdog, _ = watchdog_for(case)
    report = await watchdog.tick()
    assert report.requeued == report.failed == report.lost == 0
    assert len(case.ledger.entries) == 1 and case.dispatcher.calls == []
