import pytest

from src.app.contracts.documents.statuses import DocumentStatus, PartStatus
from src.app.contracts.progress import ProgressEventType
from src.app.contracts.quota import LedgerOp
from tests.support.fixtures.solver import RecoveryFixture, build_recovery

pytestmark = pytest.mark.unit


def stages(case: RecoveryFixture) -> list[tuple[ProgressEventType, str | None]]:
    return [(event[1], event[3]) for event in case.notifier.events]


async def test_first_attempt_is_requeued() -> None:
    case = await build_recovery(PartStatus.MAIN_PASS, 1)
    await case.recovery.retry_or_fail(case.part.id, reason="watchdog")
    part = await case.parts.get(case.part.id)
    assert part is not None and part.status is PartStatus.QUEUED and part.attempts == 1
    assert case.dispatcher.calls == [("enqueue_part", (case.part.id, False))]
    assert stages(case) == [(ProgressEventType.PART_STATUS, PartStatus.QUEUED.value)]


async def test_soft_limit_publishes_queued_status() -> None:
    case = await build_recovery(PartStatus.MAIN_PASS, 1)
    await case.recovery.retry_or_fail(case.part.id, reason="soft_time_limit")
    assert stages(case) == [(ProgressEventType.PART_STATUS, PartStatus.QUEUED.value)]
    part = await case.parts.get(case.part.id)
    assert part is not None and part.status is PartStatus.QUEUED and part.error == "soft_time_limit"


async def test_exhausted_attempt_is_failed_and_refunded_once() -> None:
    case = await build_recovery(PartStatus.MAIN_PASS, 2)
    await case.recovery.retry_or_fail(case.part.id, reason="watchdog")
    await case.recovery.retry_or_fail(case.part.id, reason="duplicate")
    part = await case.parts.get(case.part.id)
    assert part is not None and part.status is PartStatus.FAILED
    assert [entry.op for entry in case.ledger.entries] == [LedgerOp.RESERVE, LedgerOp.REFUND]
    assert case.documents.refreshed == [case.part.document_id]
    assert case.dispatcher.calls == []
    assert stages(case) == [
        (ProgressEventType.PART_STATUS, PartStatus.FAILED.value),
        (ProgressEventType.DOCUMENT_DONE, None),
    ]
    document = await case.documents.get(case.document.id)
    assert document is not None and document.status is DocumentStatus.FAILED


async def test_pipeline_error_publishes_failed_and_document_done() -> None:
    case = await build_recovery(PartStatus.MAIN_PASS, 1)
    await case.recovery.fail(case.part.id, reason="pipeline_error")
    part = await case.parts.get(case.part.id)
    assert part is not None and part.status is PartStatus.FAILED and part.error == "pipeline_error"
    assert stages(case) == [
        (ProgressEventType.PART_STATUS, PartStatus.FAILED.value),
        (ProgressEventType.DOCUMENT_DONE, None),
    ]


async def test_requeue_events_are_published_after_commit() -> None:
    case = await build_recovery(PartStatus.MAIN_PASS, 1)
    await case.recovery.retry_or_fail(case.part.id, reason="soft_time_limit")
    assert case.session.committed == 1
    assert case.notifier.committed_at_emit == [1]


async def test_failure_events_are_published_after_commit() -> None:
    case = await build_recovery(PartStatus.MAIN_PASS, 2)
    await case.recovery.fail(case.part.id, reason="pipeline_error")
    assert case.session.committed == 1
    assert case.notifier.committed_at_emit == [1, 1]


async def test_published_part_is_ignored() -> None:
    case = await build_recovery(PartStatus.PUBLISHED, 1)
    await case.recovery.retry_or_fail(case.part.id, reason="watchdog")
    part = await case.parts.get(case.part.id)
    assert part is not None and part.status is PartStatus.PUBLISHED
    assert len(case.ledger.entries) == 1 and case.dispatcher.calls == []
    assert stages(case) == []
