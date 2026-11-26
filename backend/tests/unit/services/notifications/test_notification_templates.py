"""Public completion-email behavior with a recording transport."""

import os
import subprocess
import sys
from dataclasses import replace
from typing import cast

import pytest
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.contracts.documents.part_draft import PartDraft
from src.app.contracts.documents.statuses import DocumentStatus, PartStatus, SourceType
from src.app.core.settings.app import AppSettings
from src.app.core.settings.smtp import SMTPSettings, validate_smtp_config
from src.app.observability.notification_claims import RedisNotificationClaims
from src.app.services.notifications.notification_service import NotificationService
from tests.support.fakes.db.session import FakeSession
from tests.support.fakes.notifications.email_sender import FakeEmailSender
from tests.support.fakes.repositories.documents import FakeDocumentPartRepository, FakeDocumentRepository
from tests.support.fakes.repositories.users import FakeUserRepository

pytestmark = pytest.mark.unit


class ClaimRedis:
    def __init__(self) -> None:
        self.claims: dict[str, str] = {}

    async def set(self, key: str, value: str, *, nx: bool, ex: int) -> bool:
        assert nx and ex > 0
        if key in self.claims:
            return False
        self.claims[key] = value
        return True

    async def delete(self, key: str) -> int:
        return int(self.claims.pop(key, None) is not None)

    async def eval(self, script: str, numkeys: int, key: str, claim: str) -> int:
        assert numkeys == 1 and script
        return await self.delete(key) if self.claims.get(key) == claim else 0


@pytest.mark.parametrize("locale", ["ru", "en"])
async def test_email_is_rendered_once_in_owner_language_and_escaped(locale: str) -> None:
    users = FakeUserRepository()
    documents = FakeDocumentRepository()
    parts = FakeDocumentPartRepository()
    redis = ClaimRedis()
    sender = FakeEmailSender()
    owner = await users.create(email="owner@example.com", password_hash="hash")
    users._users[owner.id] = replace(owner, locale=locale)
    document = await documents.create(
        owner_id=owner.id,
        title="<Physics & Math>",
        source_type=SourceType.UPLOAD,
        object_key="source.md",
        mime_type="text/markdown",
        size_bytes=1,
        checksum="a" * 64,
    )
    await documents.set_status(document.id, DocumentStatus.DONE)
    service = NotificationService(
        session_factory=cast(async_sessionmaker[AsyncSession], lambda: FakeSession()),
        users=lambda _: users,
        documents=lambda _: documents,
        parts=lambda _: parts,
        claims=RedisNotificationClaims(cast(Redis, redis)),
        sender=sender,
        app_settings=AppSettings(public_app_url="https://app.example/"),
        smtp_settings=SMTPSettings(enabled=True, host="localhost"),
    )
    await service.on_document_finished(document.id)
    await service.on_document_finished(document.id)
    assert len(sender.sent) == 1
    email = sender.sent[0]
    assert "&lt;Physics &amp; Math&gt;" in email.html
    assert f"https://app.example/{locale}/documents/{document.id}" in email.text
    assert f"https://app.example/{locale}/profile" in email.text
    assert email.subject and ("Could not prepare" in email.subject) == (locale == "en")


async def test_email_failure_is_retryable_and_disabled_does_not_claim() -> None:
    redis, sender = ClaimRedis(), FakeEmailSender(RuntimeError("smtp unavailable"))
    users, documents, parts = FakeUserRepository(), FakeDocumentRepository(), FakeDocumentPartRepository()
    owner = await users.create(email="owner@example.com", password_hash="hash")
    document = await documents.create(
        owner_id=owner.id,
        title="Test",
        source_type=SourceType.UPLOAD,
        object_key="source.md",
        mime_type="text/markdown",
        size_bytes=1,
        checksum="a" * 64,
    )
    await documents.set_status(document.id, DocumentStatus.DONE)

    def service(enabled: bool) -> NotificationService:
        return NotificationService(
            session_factory=cast(async_sessionmaker[AsyncSession], lambda: FakeSession()),
            users=lambda _: users,
            documents=lambda _: documents,
            parts=lambda _: parts,
            claims=RedisNotificationClaims(cast(Redis, redis)),
            sender=sender,
            app_settings=AppSettings(),
            smtp_settings=SMTPSettings(enabled=enabled, host="localhost"),
        )

    await service(False).on_document_finished(document.id)
    assert not redis.claims and not sender.sent
    enabled_service = service(True)
    await enabled_service.on_document_finished(document.id)
    assert not redis.claims
    sender.error = None
    await enabled_service.on_document_finished(document.id)
    assert len(sender.sent) == 1
    await documents.set_status(document.id, DocumentStatus.PARSED)
    await redis.delete(f"notified:{document.id}")
    await enabled_service.on_document_finished(document.id)
    assert len(sender.sent) == 1 and not redis.claims
    await documents.set_status(document.id, DocumentStatus.DONE)
    users._users[owner.id] = replace(users._users[owner.id], notify_email=False)
    await enabled_service.on_document_finished(document.id)
    assert not redis.claims and len(sender.sent) == 1


def test_production_rejects_mailpit() -> None:
    with pytest.raises(ValueError, match="SMTP_HOST"):
        validate_smtp_config("production", SMTPSettings(enabled=True, host="mailpit"))


@pytest.mark.parametrize("module", ["src.main", "src.worker"])
def test_api_and_worker_refuse_invalid_production_smtp(module: str) -> None:
    env = {
        **os.environ,
        "ENVIRONMENT": "production",
        "SMTP_ENABLED": "true",
        "SMTP_HOST": "mailpit",
        "AUTH_JWT_SECRET": "test-secret-key-must-be-at-least-32-chars-long",
    }
    result = subprocess.run([sys.executable, "-c", f"import {module}"], env=env, capture_output=True, text=True)
    assert result.returncode != 0 and "SMTP_HOST" in result.stderr


@pytest.mark.parametrize(
    ("statuses", "expected_subject", "expected_text"),
    [
        ([PartStatus.PUBLISHED, PartStatus.PUBLISHED], "ready", "parts: 2"),
        ([PartStatus.PUBLISHED, PartStatus.FAILED], "partially", "1 of 2 ready"),
        ([PartStatus.FAILED, PartStatus.FAILED], "Could not", "Generations have been returned"),
    ],
)
async def test_email_outcomes_from_current_run_only(
    statuses: list[PartStatus],
    expected_subject: str,
    expected_text: str,
) -> None:
    users, documents, parts = FakeUserRepository(), FakeDocumentRepository(), FakeDocumentPartRepository()
    owner = await users.create(email="owner@example.com", password_hash="hash", locale="en")
    document = await documents.create(
        owner_id=owner.id,
        title="Lesson",
        source_type=SourceType.UPLOAD,
        object_key="source.md",
        mime_type="text/markdown",
        size_bytes=1,
        checksum="a" * 64,
    )
    drafts = [
        PartDraft(
            index=index, title="Part", topic_ids=[], source_markdown="text", token_count=1, quota_period_start=None
        )
        for index in range(3)
    ]
    old, *current = await parts.add_many(document.id, drafts)
    await parts.transition(old.id, frozenset({PartStatus.QUEUED}), PartStatus.PUBLISHED)
    for part, status in zip(current, statuses, strict=True):
        await parts.transition(part.id, frozenset({PartStatus.QUEUED}), status)
    await documents.set_generation_start(document.id, 1)
    await documents.set_status(
        document.id, DocumentStatus.DONE if PartStatus.PUBLISHED in statuses else DocumentStatus.FAILED
    )
    sender = FakeEmailSender()
    service = NotificationService(
        session_factory=cast(async_sessionmaker[AsyncSession], lambda: FakeSession()),
        users=lambda _: users,
        documents=lambda _: documents,
        parts=lambda _: parts,
        claims=RedisNotificationClaims(cast(Redis, ClaimRedis())),
        sender=sender,
        app_settings=AppSettings(),
        smtp_settings=SMTPSettings(enabled=True, host="localhost"),
    )
    await service.on_document_finished(document.id)
    assert len(sender.sent) == 1
    assert expected_subject in sender.sent[0].subject
    assert expected_text in sender.sent[0].text
