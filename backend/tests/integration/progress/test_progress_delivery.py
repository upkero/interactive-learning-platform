"""Acceptance checks against PostgreSQL, Redis Streams, HTTP SSE and Mailpit."""

import asyncio
import json
import logging
import os
import socket
import sys
import time
from collections.abc import AsyncIterator, Iterator
from typing import Protocol, cast
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from redis.asyncio import Redis
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.api.v1.middleware.rate_limit import limiter
from src.app.bootstrap.container import ApplicationContainer
from src.app.contracts.documents.part_draft import PartDraft
from src.app.contracts.documents.statuses import DocumentStatus, MaterialRole, PartStatus, SourceType
from src.app.contracts.progress import ProgressEventType
from src.app.contracts.progress.stream import stream_key
from src.app.core.settings.app import get_app_settings
from src.app.core.settings.progress import ProgressSettings, get_progress_settings
from src.app.core.settings.smtp import SMTPSettings, get_smtp_settings
from src.app.models.user import User
from src.app.observability.notification_claims import RedisNotificationClaims
from src.app.observability.progress_notifier import RedisProgressNotifier
from src.app.repositories.document_part_repository import DocumentPartRepository
from src.app.repositories.document_repository import DocumentRepository
from src.app.repositories.user_material_repository import UserMaterialRepository
from src.app.repositories.user_repository import UserRepository
from src.app.services.notifications.email_sender import EmailSender
from src.app.services.notifications.notification_service import NotificationService
from src.app.services.progress.progress_reader import ProgressReader
from src.app.services.quota.quota_ledger import QuotaLedger
from src.app.storage.object_keys import parsed_markdown_key
from src.app.tasks.parts import process_part
from src.main import create_app
from tests.support.fakes.services.task_dispatcher import FakeTaskDispatcher
from tests.support.fakes.storage.object_storage_client import FakeObjectStorageClient
from tests.support.fixtures.documents import topic_node

pytestmark = pytest.mark.integration


@pytest.fixture
async def progress_redis() -> AsyncIterator[Redis]:
    url = os.environ.get("REDIS_PROGRESS_URL")
    if not url:
        if os.environ.get("CI"):
            pytest.fail("REDIS_PROGRESS_URL must point to isolated Redis in CI")
        pytest.skip("Set REDIS_PROGRESS_URL to an isolated Redis database")
    client = Redis.from_url(url)
    try:
        await client.ping()
        yield client
    finally:
        await client.aclose()


@pytest.fixture
def client(session_factory: async_sessionmaker[AsyncSession]) -> Iterator[TestClient]:
    limiter.reset()
    with TestClient(create_app()) as instance:
        yield instance


async def _document(
    session_factory: async_sessionmaker[AsyncSession], *, status: DocumentStatus = DocumentStatus.DONE
) -> tuple[UUID, str]:
    email = f"progress-{uuid4()}@example.com"
    async with session_factory() as session, session.begin():
        owner = await UserRepository(session).create(email=email, password_hash="hash", monthly_limit=20)
        document = await DocumentRepository(session).create(
            owner_id=owner.id,
            title="Progress example",
            source_type=SourceType.UPLOAD,
            object_key="demo.md",
            mime_type="text/markdown",
            size_bytes=1,
            checksum="a" * 64,
        )
        await DocumentRepository(session).set_status(document.id, status)
        await UserMaterialRepository(session).create(user_id=owner.id, document_id=document.id, role=MaterialRole.OWNER)
    return document.id, email


class ResponseText(Protocol):
    @property
    def text(self) -> str: ...


def _sse(response: ResponseText) -> list[tuple[str, str]]:
    blocks = [block for block in response.text.split("\r\n\r\n") if "data: " in block]
    return [
        (
            next(line[4:] for line in block.splitlines() if line.startswith("id: ")),
            next(line[6:] for line in block.splitlines() if line.startswith("data: ")),
        )
        for block in blocks
    ]


async def _mailpit_count(api_url: str, email: str) -> int:
    async with httpx.AsyncClient() as http:
        response = await http.get(f"{api_url}/api/v1/messages", params={"limit": 100}, timeout=5)
        response.raise_for_status()
        return sum(
            any(recipient["Address"] == email for recipient in message["To"]) for message in response.json()["messages"]
        )


async def test_real_redis_stream_maxlen_ttl_and_failure_warning(
    progress_redis: Redis, caplog: pytest.LogCaptureFixture
) -> None:
    document_id = uuid4()
    notifier = RedisProgressNotifier(progress_redis, ProgressSettings(stream_maxlen=10))
    try:
        for index in range(240):
            await notifier.emit(document_id, ProgressEventType.PART_STATUS, stage="queued", message=f"queued {index}")
        assert 0 < await progress_redis.xlen(stream_key(document_id)) <= 110
        assert 0 < await progress_redis.ttl(stream_key(document_id)) <= 86400
        row = (await progress_redis.xrange(stream_key(document_id)))[0]
        assert json.loads(row[1][b"data"])["ts"]
    finally:
        await progress_redis.delete(stream_key(document_id))

    broken = Redis.from_url("redis://127.0.0.1:6390/14", socket_connect_timeout=0.2)
    try:
        assert (
            await RedisProgressNotifier(broken, ProgressSettings()).emit(
                document_id, ProgressEventType.ERROR, message="error"
            )
            is None
        )
        assert "Progress event was not published" in caplog.text
    finally:
        await broken.aclose()


async def test_real_progress_reset_deletes_stream(progress_redis: Redis) -> None:
    document_id = uuid4()
    notifier = RedisProgressNotifier(progress_redis, ProgressSettings())
    key = stream_key(document_id)
    await notifier.emit(document_id, ProgressEventType.PART_STATUS, message="old run")
    assert await progress_redis.exists(key) == 1
    await notifier.reset(document_id)
    assert await progress_redis.exists(key) == 0


async def test_reader_reconnect_and_terminal_tail(progress_redis: Redis) -> None:
    document_id = uuid4()
    notifier = RedisProgressNotifier(progress_redis, ProgressSettings())
    try:
        for index in range(3):
            await notifier.emit(document_id, ProgressEventType.PART_STATUS, message=str(index))
        reader = ProgressReader(progress_redis)
        stream = reader.follow(document_id, "0-0", finished_status=DocumentStatus.GENERATING, run_outcome="ready")
        first = [await stream.__anext__() for _ in range(3)]
        for index in range(3, 5):
            await notifier.emit(document_id, ProgressEventType.PART_STATUS, message=str(index))
        after = [await stream.__anext__() for _ in range(2)]
        await stream.aclose()
        assert [json.loads(entry.data)["message"] for entry in after] == ["3", "4"]
        resumed = []
        async for entry in reader.follow(
            document_id, first[-1].id, finished_status=DocumentStatus.DONE, run_outcome="ready", locale="en"
        ):
            resumed.append(entry)
        assert [json.loads(entry.data)["message"] for entry in resumed[:2]] == ["3", "4"]
        assert resumed[-1].type == "document_done" and "Your material" in resumed[-1].data
        closed = [
            entry
            async for entry in reader.follow(
                document_id, resumed[-1].id, finished_status=DocumentStatus.DONE, run_outcome="ready", locale="en"
            )
        ]
        assert len(closed) == 1 and closed[0].type == "document_done"
    finally:
        await progress_redis.delete(stream_key(document_id))


async def test_http_reconnect_after_three_events_receives_exactly_two(
    session_factory: async_sessionmaker[AsyncSession],
    progress_redis: Redis,
) -> None:
    """A real HTTP client disconnects before the worker appends its last two records."""
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    server = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "uvicorn",
        "src.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    document_id = uuid4()
    try:
        async with httpx.AsyncClient(base_url=base, timeout=8) as http:
            for _ in range(150):
                try:
                    if (await http.get("/health/live")).status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                if server.returncode is not None:
                    pytest.fail(f"Isolated HTTP server exited with code {server.returncode}")
                await asyncio.sleep(0.1)
            else:
                pytest.fail("Isolated HTTP server did not start")
            response = await http.post(
                "/api/v1/auth/register",
                json={"email": f"stream-{uuid4()}@example.com", "password": "long-password"},
            )
            assert response.status_code == 201, response.text
            owner_id = UUID(response.json()["id"])
            async with session_factory() as session, session.begin():
                await DocumentRepository(session).create(
                    id=document_id,
                    owner_id=owner_id,
                    title="Streaming",
                    source_type=SourceType.UPLOAD,
                    object_key="source.md",
                    mime_type="text/markdown",
                    size_bytes=1,
                    checksum="a" * 64,
                )
                await DocumentRepository(session).set_status(document_id, DocumentStatus.GENERATING)
                await UserMaterialRepository(session).create(
                    user_id=owner_id,
                    document_id=document_id,
                    role=MaterialRole.OWNER,
                )
            notifier = RedisProgressNotifier(progress_redis, ProgressSettings())
            for index in range(3):
                await notifier.emit(document_id, ProgressEventType.PART_STATUS, message=f"event {index}")
            ids: list[str] = []
            received = 0
            async with http.stream("GET", f"/api/v1/documents/{document_id}/events") as stream:
                assert stream.status_code == 200
                async for line in stream.aiter_lines():
                    if line.startswith("id: "):
                        ids.append(line[4:])
                    if line.startswith("data: "):
                        received += 1
                    if received == 3:
                        break
            await notifier.emit(document_id, ProgressEventType.PART_STATUS, message="event 3")
            async with session_factory() as session, session.begin():
                await DocumentRepository(session).set_status(document_id, DocumentStatus.DONE)
            await notifier.emit(document_id, ProgressEventType.DOCUMENT_DONE, message="event 4")
            async with http.stream(
                "GET",
                f"/api/v1/documents/{document_id}/events",
                headers={"Last-Event-ID": ids[2]},
            ) as stream:
                text = (await stream.aread()).decode()
            frames = [block for block in text.split("\r\n\r\n") if "data: " in block]
            assert len(frames) == 2
            assert '"message": "event 3"' in frames[0]
            assert '"message": "event 4"' in frames[1]
    finally:
        server.terminate()
        await asyncio.wait_for(server.wait(), timeout=5)
        await progress_redis.delete(stream_key(document_id))


async def test_sse_authorization_header_priority_and_terminal_close(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession], progress_redis: Redis
) -> None:
    # Register through HTTP to obtain a real session cookie.
    registered = client.post(
        "/api/v1/auth/register", json={"email": f"reader-{uuid4()}@example.com", "password": "long-password"}
    )
    assert registered.status_code == 201, registered.text
    owner_id = UUID(registered.json()["id"])
    document_id = uuid4()
    async with session_factory() as session, session.begin():
        await DocumentRepository(session).create(
            id=document_id,
            owner_id=owner_id,
            title="SSE",
            source_type=SourceType.UPLOAD,
            object_key="source.md",
            mime_type="text/markdown",
            size_bytes=1,
            checksum="a" * 64,
        )
        await DocumentRepository(session).set_status(document_id, DocumentStatus.DONE)
        await UserMaterialRepository(session).create(user_id=owner_id, document_id=document_id, role=MaterialRole.OWNER)
    notifier = RedisProgressNotifier(progress_redis, ProgressSettings())
    try:
        foreign_id, _ = await _document(session_factory)
        assert client.get(f"/api/v1/documents/{foreign_id}/events").status_code == 404
        for index in range(3):
            await notifier.emit(document_id, ProgressEventType.PART_STATUS, message=str(index))
        entries = await progress_redis.xrange(stream_key(document_id))
        third = entries[-1][0].decode()
        for index in range(3, 5):
            await notifier.emit(document_id, ProgressEventType.PART_STATUS, message=str(index))
        await notifier.emit(document_id, ProgressEventType.DOCUMENT_DONE, message="Done")
        response = client.get(
            f"/api/v1/documents/{document_id}/events?last_event_id={entries[0][0].decode()}",
            headers={"Last-Event-ID": third},
            timeout=3,
        )
        assert response.status_code == 200
        assert [json.loads(data)["message"] for _, data in _sse(response)] == ["3", "4", "Done"]
        again = client.get(f"/api/v1/documents/{document_id}/events", headers={"Last-Event-ID": third}, timeout=3)
        assert again.status_code == 200 and len(_sse(again)) == 3
        by_query = client.get(f"/api/v1/documents/{document_id}/events?last_event_id={third}", timeout=3)
        assert [json.loads(data)["message"] for _, data in _sse(by_query)] == ["3", "4", "Done"]
        tail = (await progress_redis.xrevrange(stream_key(document_id), count=1))[0][0].decode()
        synthetic = client.get(f"/api/v1/documents/{document_id}/events", headers={"Last-Event-ID": tail}, timeout=3)
        assert synthetic.status_code == 200 and len(_sse(synthetic)) == 1
        assert json.loads(_sse(synthetic)[0][1])["ts"]
        await progress_redis.delete(stream_key(document_id))
        started = time.monotonic()
        expired = client.get(f"/api/v1/documents/{document_id}/events", timeout=3)
        elapsed = time.monotonic() - started
        assert expired.status_code == 200 and len(_sse(expired)) == 1 and elapsed < 1
    finally:
        await progress_redis.delete(stream_key(document_id))


async def test_http_second_run_without_cursor_only_returns_new_stream(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession], progress_redis: Redis
) -> None:
    registered = client.post(
        "/api/v1/auth/register", json={"email": f"rerun-{uuid4()}@example.com", "password": "long-password"}
    )
    assert registered.status_code == 201, registered.text
    owner_id = UUID(registered.json()["id"])
    document_id = uuid4()
    async with session_factory() as session, session.begin():
        await DocumentRepository(session).create(
            id=document_id,
            owner_id=owner_id,
            title="Repeat",
            source_type=SourceType.UPLOAD,
            object_key="repeat.md",
            mime_type="text/markdown",
            size_bytes=1,
            checksum="b" * 64,
        )
        await DocumentRepository(session).set_status(document_id, DocumentStatus.DONE)
        await UserMaterialRepository(session).create(user_id=owner_id, document_id=document_id, role=MaterialRole.OWNER)
    notifier = RedisProgressNotifier(progress_redis, ProgressSettings())
    key = stream_key(document_id)
    try:
        await notifier.emit(document_id, ProgressEventType.PART_STATUS, message="old run")
        await notifier.emit(document_id, ProgressEventType.DOCUMENT_DONE, message="old done")
        await notifier.reset(document_id)
        async with session_factory() as session, session.begin():
            await DocumentRepository(session).set_status(document_id, DocumentStatus.GENERATING)
        await notifier.emit(document_id, ProgressEventType.PART_STATUS, message="new run")
        await notifier.emit(document_id, ProgressEventType.DOCUMENT_DONE, message="new done")
        started = time.monotonic()
        response = client.get(f"/api/v1/documents/{document_id}/events", timeout=3)
        elapsed = time.monotonic() - started
        assert response.status_code == 200 and elapsed < 1
        messages = [json.loads(data)["message"] for _, data in _sse(response)]
        assert messages == ["new run", "new done"]
    finally:
        await progress_redis.delete(key)


async def test_http_second_generate_resets_stream_and_returns_only_new_events(
    client: TestClient,
    session_factory: async_sessionmaker[AsyncSession],
    progress_redis: Redis,
    dispatcher: FakeTaskDispatcher,
) -> None:
    """Two real ``POST /generate`` calls: the second one clears the first run's stream."""
    registered = client.post(
        "/api/v1/auth/register", json={"email": f"generate-{uuid4()}@example.com", "password": "long-password"}
    )
    assert registered.status_code == 201, registered.text
    owner_id = UUID(registered.json()["id"])
    container = cast(ApplicationContainer, cast(FastAPI, client.app).state.container)
    storage = FakeObjectStorageClient()
    container.__dict__["object_storage"] = storage
    container.__dict__["task_dispatcher"] = dispatcher
    async with session_factory() as session, session.begin():
        documents = DocumentRepository(session)
        document = await documents.create(
            owner_id=owner_id,
            title="Repeat generation",
            source_type=SourceType.UPLOAD,
            object_key="repeat-generation.md",
            mime_type="text/markdown",
            size_bytes=300,
            checksum="f" * 64,
        )
        await UserMaterialRepository(session).create(user_id=owner_id, document_id=document.id, role=MaterialRole.OWNER)
        await documents.set_status(document.id, DocumentStatus.PARSED)
        await documents.set_topic_tree(document.id, [topic_node("topic-0", "Topic 0", 0, 100, 20)])
    await storage.put_object(
        bucket="documents",
        key=parsed_markdown_key(owner_id, document.id),
        data=b"a" * 300,
        content_type="text/markdown",
    )
    body = {"topic_ids": ["topic-0"], "answers": {"level": "novice", "goal": "exam", "depth": "standard"}}
    notifier = RedisProgressNotifier(progress_redis, ProgressSettings())
    key = stream_key(document.id)
    try:
        first = client.post(f"/api/v1/documents/{document.id}/generate", json=body)
        assert first.status_code == 202, first.text
        first_part = UUID(first.json()["part_ids"][0])
        async with session_factory() as session, session.begin():
            await DocumentPartRepository(session).transition(
                first_part, frozenset({PartStatus.QUEUED}), PartStatus.PUBLISHED
            )
            await DocumentRepository(session).refresh_status(document.id)
        await notifier.emit(document.id, ProgressEventType.PART_STATUS, message="first run")
        await notifier.emit(document.id, ProgressEventType.DOCUMENT_DONE, stage="done", message="first run done")
        assert await progress_redis.exists(key) == 1

        second = client.post(f"/api/v1/documents/{document.id}/generate", json=body)
        assert second.status_code == 202, second.text
        # The reset happened inside the HTTP request, before the response.
        assert await progress_redis.exists(key) == 0

        second_part = UUID(second.json()["part_ids"][0])
        async with session_factory() as session, session.begin():
            await DocumentPartRepository(session).transition(
                second_part, frozenset({PartStatus.QUEUED}), PartStatus.PUBLISHED
            )
            await DocumentRepository(session).refresh_status(document.id)
        await notifier.emit(document.id, ProgressEventType.PART_STATUS, message="second run")
        await notifier.emit(document.id, ProgressEventType.DOCUMENT_DONE, stage="done", message="second run done")

        started = time.monotonic()
        response = client.get(f"/api/v1/documents/{document.id}/events", timeout=3)
        elapsed = time.monotonic() - started
        assert response.status_code == 200 and elapsed < 1
        assert [json.loads(data)["message"] for _, data in _sse(response)] == ["second run", "second run done"]
    finally:
        await progress_redis.delete(key)


async def test_synthetic_document_done_uses_current_run_outcome(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession], progress_redis: Redis
) -> None:
    """A lost stream must still report the failure of the latest run."""
    registered = client.post(
        "/api/v1/auth/register", json={"email": f"synthetic-{uuid4()}@example.com", "password": "long-password"}
    )
    assert registered.status_code == 201, registered.text
    owner_id = UUID(registered.json()["id"])
    async with session_factory() as session, session.begin():
        documents = DocumentRepository(session)
        materials = UserMaterialRepository(session)
        parts = DocumentPartRepository(session)

        failed_document = await documents.create(
            owner_id=owner_id,
            title="Failed rerun",
            source_type=SourceType.UPLOAD,
            object_key="failed-rerun.md",
            mime_type="text/markdown",
            size_bytes=1,
            checksum="1" * 64,
        )
        await materials.create(user_id=owner_id, document_id=failed_document.id, role=MaterialRole.OWNER)
        old_part, current_part = await parts.add_many(
            failed_document.id,
            [
                PartDraft(
                    index=0,
                    title="old",
                    topic_ids=[],
                    source_markdown="x",
                    token_count=1,
                    quota_period_start=None,
                ),
                PartDraft(
                    index=1,
                    title="current",
                    topic_ids=[],
                    source_markdown="x",
                    token_count=1,
                    quota_period_start=None,
                ),
            ],
        )
        await parts.transition(old_part.id, frozenset({PartStatus.QUEUED}), PartStatus.PUBLISHED)
        await parts.transition(current_part.id, frozenset({PartStatus.QUEUED}), PartStatus.FAILED)
        await documents.set_generation_start(failed_document.id, 1)
        await documents.set_status(failed_document.id, DocumentStatus.DONE)

        ready_document = await documents.create(
            owner_id=owner_id,
            title="Ready rerun",
            source_type=SourceType.UPLOAD,
            object_key="ready-rerun.md",
            mime_type="text/markdown",
            size_bytes=1,
            checksum="2" * 64,
        )
        await materials.create(user_id=owner_id, document_id=ready_document.id, role=MaterialRole.OWNER)
        ready_old, ready_current = await parts.add_many(
            ready_document.id,
            [
                PartDraft(
                    index=0,
                    title="old",
                    topic_ids=[],
                    source_markdown="x",
                    token_count=1,
                    quota_period_start=None,
                ),
                PartDraft(
                    index=1,
                    title="current",
                    topic_ids=[],
                    source_markdown="x",
                    token_count=1,
                    quota_period_start=None,
                ),
            ],
        )
        await parts.transition(ready_old.id, frozenset({PartStatus.QUEUED}), PartStatus.PUBLISHED)
        await parts.transition(ready_current.id, frozenset({PartStatus.QUEUED}), PartStatus.PUBLISHED)
        await documents.set_generation_start(ready_document.id, 1)
        await documents.set_status(ready_document.id, DocumentStatus.DONE)

    try:
        await progress_redis.delete(stream_key(failed_document.id))
        started = time.monotonic()
        failed_response = client.get(f"/api/v1/documents/{failed_document.id}/events", timeout=3)
        elapsed = time.monotonic() - started
        assert failed_response.status_code == 200 and elapsed < 1
        ((_, failed_data),) = _sse(failed_response)
        failed_event = json.loads(failed_data)
        assert failed_event["type"] == "document_done"
        assert failed_event["stage"] == "done"
        assert failed_event["message"] == "Не получилось подготовить материал"  # noqa: RUF001

        await progress_redis.delete(stream_key(ready_document.id))
        ready_response = client.get(f"/api/v1/documents/{ready_document.id}/events", timeout=3)
        assert ready_response.status_code == 200
        ((_, ready_data),) = _sse(ready_response)
        ready_event = json.loads(ready_data)
        assert ready_event["type"] == "document_done"
        assert ready_event["stage"] == "done"
        assert ready_event["message"] == "Материал готов"
    finally:
        await progress_redis.delete(stream_key(failed_document.id))
        await progress_redis.delete(stream_key(ready_document.id))


async def test_real_document_status_keeps_done_after_failed_rerun(
    session_factory: async_sessionmaker[AsyncSession], ledger: QuotaLedger
) -> None:
    async with session_factory() as session, session.begin():
        owner = await UserRepository(session).create(
            email=f"status-{uuid4()}@example.com", password_hash="hash", monthly_limit=20
        )
        document = await DocumentRepository(session).create(
            owner_id=owner.id,
            title="Status",
            source_type=SourceType.UPLOAD,
            object_key="status.md",
            mime_type="text/markdown",
            size_bytes=1,
            checksum="c" * 64,
        )
        quota = await ledger.reserve(session, user_id=owner.id, document_id=document.id, parts=2)
        parts = await DocumentPartRepository(session).add_many(
            document.id,
            [
                PartDraft(
                    index=0,
                    title="old",
                    topic_ids=[],
                    source_markdown="x",
                    token_count=1,
                    quota_period_start=quota.period.start,
                ),
                PartDraft(
                    index=1,
                    title="new",
                    topic_ids=[],
                    source_markdown="x",
                    token_count=1,
                    quota_period_start=quota.period.start,
                ),
            ],
        )
        await DocumentPartRepository(session).transition(
            parts[0].id, frozenset({parts[0].status}), PartStatus.PUBLISHED
        )
        await DocumentRepository(session).set_generation_start(document.id, 1)
        await DocumentRepository(session).set_status(document.id, DocumentStatus.GENERATING)
        await DocumentPartRepository(session).transition(parts[1].id, frozenset({parts[1].status}), PartStatus.FAILED)
        await DocumentRepository(session).refresh_status(document.id)
        saved = await DocumentRepository(session).get(document.id)
    assert saved is not None and saved.status is DocumentStatus.DONE

    async with session_factory() as session, session.begin():
        owner = await UserRepository(session).create(
            email=f"failed-{uuid4()}@example.com", password_hash="hash", monthly_limit=20
        )
        document = await DocumentRepository(session).create(
            owner_id=owner.id,
            title="Failed",
            source_type=SourceType.UPLOAD,
            object_key="failed.md",
            mime_type="text/markdown",
            size_bytes=1,
            checksum="d" * 64,
        )
        quota = await ledger.reserve(session, user_id=owner.id, document_id=document.id, parts=1)
        (part,) = await DocumentPartRepository(session).add_many(
            document.id,
            [
                PartDraft(
                    index=0,
                    title="only",
                    topic_ids=[],
                    source_markdown="x",
                    token_count=1,
                    quota_period_start=quota.period.start,
                )
            ],
        )
        await DocumentRepository(session).set_status(document.id, DocumentStatus.GENERATING)
        await DocumentPartRepository(session).transition(part.id, frozenset({part.status}), PartStatus.FAILED)
        await DocumentRepository(session).refresh_status(document.id)
        saved = await DocumentRepository(session).get(document.id)
    assert saved is not None and saved.status is DocumentStatus.FAILED


async def test_mailpit_delivery_once_and_disabled_user(
    session_factory: async_sessionmaker[AsyncSession], progress_redis: Redis
) -> None:
    document_id, email = await _document(session_factory)
    settings = SMTPSettings(
        enabled=True,
        host=os.environ.get("SMTP_HOST", "localhost"),
        port=int(os.environ.get("SMTP_PORT", "1025")),
    )
    mailpit_url = os.environ.get("TEST_MAILPIT_API_URL", "http://localhost:8025")
    service = NotificationService(
        session_factory=session_factory,
        users=UserRepository,
        documents=DocumentRepository,
        parts=DocumentPartRepository,
        claims=RedisNotificationClaims(progress_redis),
        sender=EmailSender(settings),
        app_settings=get_app_settings(),
        smtp_settings=settings,
    )
    try:
        await service.on_document_finished(document_id)
        await service.on_document_finished(document_id)
        assert await _mailpit_count(mailpit_url, email) == 1
        disabled_id, disabled_email = await _document(session_factory)
        async with session_factory() as session, session.begin():
            await session.execute(update(User).where(User.email == disabled_email).values(notify_email=False))
        await service.on_document_finished(disabled_id)
        assert not await progress_redis.exists(f"notified:{disabled_id}")
        assert await _mailpit_count(mailpit_url, disabled_email) == 0
    finally:
        await progress_redis.delete(f"notified:{document_id}")


async def test_process_part_delivers_completion_email_to_mailpit(
    session_factory: async_sessionmaker[AsyncSession],
    ledger: QuotaLedger,
    progress_redis: Redis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REDIS_PROGRESS_URL", os.environ["REDIS_PROGRESS_URL"])
    monkeypatch.setenv("SMTP_ENABLED", "true")
    monkeypatch.setenv("SMTP_HOST", os.environ.get("SMTP_HOST", "localhost"))
    monkeypatch.setenv("SMTP_PORT", os.environ.get("SMTP_PORT", "1025"))
    get_progress_settings.cache_clear()
    get_smtp_settings.cache_clear()
    email = f"worker-mail-{uuid4()}@example.com"
    async with session_factory() as session, session.begin():
        owner = await UserRepository(session).create(email=email, password_hash="hash", monthly_limit=20)
        document = await DocumentRepository(session).create(
            owner_id=owner.id,
            title="Worker mail",
            source_type=SourceType.UPLOAD,
            object_key="worker-mail.md",
            mime_type="text/markdown",
            size_bytes=1,
            checksum="e" * 64,
        )
        await DocumentRepository(session).set_status(document.id, DocumentStatus.GENERATING)
        quota = await ledger.reserve(session, user_id=owner.id, document_id=document.id, parts=1)
        await DocumentPartRepository(session).add_many(
            document.id,
            [
                PartDraft(
                    index=0,
                    title="Part",
                    topic_ids=[],
                    source_markdown="x",
                    token_count=1,
                    quota_period_start=quota.period.start,
                )
            ],
        )
    try:
        async with session_factory() as session:
            part = (await DocumentPartRepository(session).list_by_document(document.id))[0]
        await asyncio.to_thread(process_part.run, str(part.id))
        mailpit_url = os.environ.get("TEST_MAILPIT_API_URL", "http://localhost:8025")
        for _ in range(20):
            if await _mailpit_count(mailpit_url, email) == 1:
                break
            await asyncio.sleep(0.1)
        assert await _mailpit_count(mailpit_url, email) == 1
    finally:
        await progress_redis.delete(f"notified:{document.id}")
        await progress_redis.delete(stream_key(document.id))
        get_progress_settings.cache_clear()
        get_smtp_settings.cache_clear()


async def test_worker_succeeds_when_progress_redis_is_down(
    session_factory: async_sessionmaker[AsyncSession],
    ledger: QuotaLedger,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    async with session_factory() as session, session.begin():
        owner = await UserRepository(session).create(
            email=f"broken-redis-{uuid4()}@example.com", password_hash="hash", monthly_limit=20
        )
        document = await DocumentRepository(session).create(
            owner_id=owner.id,
            title="Redis outage",
            source_type=SourceType.UPLOAD,
            object_key="source.md",
            mime_type="text/markdown",
            size_bytes=1,
            checksum="a" * 64,
        )
        await DocumentRepository(session).set_status(document.id, DocumentStatus.GENERATING)
        quota = await ledger.reserve(session, user_id=owner.id, document_id=document.id, parts=1)
        (part,) = await DocumentPartRepository(session).add_many(
            document.id,
            [
                PartDraft(
                    index=0,
                    title="Chapter",
                    topic_ids=[],
                    source_markdown="# Chapter",
                    token_count=10,
                    quota_period_start=quota.period.start,
                )
            ],
        )
    monkeypatch.setenv("REDIS_PROGRESS_URL", "redis://127.0.0.1:6390/14")
    monkeypatch.setenv("SMTP_ENABLED", "true")
    get_progress_settings.cache_clear()
    try:
        with caplog.at_level(logging.WARNING):
            await asyncio.to_thread(process_part.run, str(part.id))
        async with session_factory() as session:
            saved = await DocumentPartRepository(session).get(part.id)
            completed = await DocumentRepository(session).get(document.id)
        assert saved is not None and saved.status.value == "published"
        assert completed is not None and completed.status is DocumentStatus.DONE
        assert any(record.levelno == logging.WARNING for record in caplog.records)
        assert not any(record.levelno >= logging.ERROR for record in caplog.records)
    finally:
        get_progress_settings.cache_clear()
