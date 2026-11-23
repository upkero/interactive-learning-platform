from dataclasses import replace
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.contracts.documents.statuses import DocumentStatus, PartStatus
from src.app.contracts.progress import ProgressEventType
from src.app.contracts.quota import LedgerOp
from src.app.core.settings.app import AppSettings
from src.app.core.settings.smtp import SMTPSettings
from src.app.services.notifications.notification_service import NotificationService
from tests.support.fakes.notifications.claims import FakeNotificationClaims
from tests.support.fakes.notifications.email_sender import FakeEmailSender
from tests.support.fakes.notifications.service import FakeDocumentNotifications
from tests.support.fakes.repositories.users import FakeUserRepository
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
        (ProgressEventType.DOCUMENT_DONE, DocumentStatus.FAILED.value),
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
        (ProgressEventType.DOCUMENT_DONE, DocumentStatus.FAILED.value),
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


async def test_recovery_messages_use_owner_locale() -> None:
    case = await build_recovery(PartStatus.MAIN_PASS, 2)
    users = FakeUserRepository()
    user = await users.create(email="en@example.com", password_hash="hash", locale="en")
    users._users[case.document.owner_id] = replace(user, id=case.document.owner_id)
    case.recovery._users = lambda _: users
    await case.recovery.fail(case.part.id, reason="pipeline_error")
    messages = [event[4] for event in case.notifier.events]
    assert all(message and "{" not in message for message in messages)
    assert "Could not prepare your material" in messages


async def test_recovery_notifies_only_after_last_part_fails() -> None:
    case = await build_recovery(PartStatus.MAIN_PASS, 2)
    notifications = FakeDocumentNotifications()
    case.recovery._notifications = notifications
    await case.recovery.fail(case.part.id, reason="watchdog")
    await case.recovery.fail(case.part.id, reason="duplicate")
    assert notifications.completed == [case.document.id]
    assert case.session.committed == 2


async def test_recovery_sends_failure_email_with_refund_message() -> None:
    case = await build_recovery(PartStatus.MAIN_PASS, 2)
    users = FakeUserRepository()
    user = await users.create(email="recovery@example.com", password_hash="hash", locale="en")
    users._users[case.document.owner_id] = replace(user, id=case.document.owner_id)
    sender = FakeEmailSender()
    case.recovery._users = lambda _: users
    case.recovery._notifications = NotificationService(
        session_factory=cast(async_sessionmaker[AsyncSession], lambda: case.session),
        users=lambda _: users,
        documents=lambda _: case.documents,
        parts=lambda _: case.parts,
        claims=FakeNotificationClaims(),
        sender=sender,
        app_settings=AppSettings(),
        smtp_settings=SMTPSettings(enabled=True, host="localhost"),
    )
    await case.recovery.fail(case.part.id, reason="watchdog")
    assert len(sender.sent) == 1
    assert "Could not prepare" in sender.sent[0].subject
    assert "Generations have been returned" in sender.sent[0].text
