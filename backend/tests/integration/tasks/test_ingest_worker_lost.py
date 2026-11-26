"""A killed prefork child must not leave its document consuming capacity forever."""

import asyncio
import os
import signal
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from celery import Celery
from redis.asyncio import Redis
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.bootstrap.container import ApplicationContainer
from src.app.contracts.documents.statuses import DocumentErrorCode, DocumentStatus, SourceType
from src.app.db.parsing_lease import PostgresParsingLease
from src.app.models.document import Document
from src.app.repositories.document_part_repository import DocumentPartRepository
from src.app.repositories.document_repository import DocumentRepository
from src.app.repositories.user_repository import UserRepository
from src.app.services.solver.pipeline.watchdog import Watchdog

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
@pytest.mark.timeout(90)
async def test_killed_prefork_child_is_failed_by_watchdog(
    session_factory: async_sessionmaker[AsyncSession], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    redis_url = os.environ.get("TEST_CELERY_REDIS_URL")
    if not redis_url:
        pytest.skip("TEST_CELERY_REDIS_URL must point to an isolated Redis instance")
    monkeypatch.setenv("CELERY_BROKER_URL", redis_url)
    assert os.getuid() != 0
    async with session_factory() as session, session.begin():
        owner = await UserRepository(session).create(
            email=f"{uuid4()}@example.com", password_hash="x", monthly_limit=20
        )
        document = await DocumentRepository(session).create(
            owner_id=owner.id,
            title="Worker loss",
            source_type=SourceType.UPLOAD,
            object_key="stall.txt",
            mime_type="text/plain",
            size_bytes=4,
            checksum="f" * 64,
        )
    env = {**os.environ, "CELERY_BROKER_URL": redis_url, "PROMETHEUS_MULTIPROC_DIR": str(tmp_path)}
    log = tmp_path / "worker.log"
    output = log.open("wb")
    worker = await asyncio.to_thread(
        subprocess.Popen,
        [
            sys.executable,
            "-m",
            "celery",
            "-A",
            "tests.support.ingest_worker:celery_app",
            "worker",
            "-Q",
            "parts.high",
            "--pool=prefork",
            "--concurrency=1",
            "--loglevel=WARNING",
            "--without-gossip",
            "--without-mingle",
            "--without-heartbeat",
            "-n",
            f"ingest-loss-{uuid4()}@%h",
        ],
        env=env,
        stdout=output,
        stderr=subprocess.STDOUT,
    )
    output.close()
    redis = Redis.from_url(redis_url)
    broker = Celery("ingest_loss_probe", broker=redis_url)
    container = ApplicationContainer()
    try:
        await asyncio.to_thread(broker.send_task, "tests.ingest_stall", args=[str(document.id)], queue="parts.high")
        for _ in range(300):
            async with session_factory() as session:
                current = await DocumentRepository(session).get(document.id)
            if current is not None and current.status is DocumentStatus.PARSING:
                break
            assert worker.poll() is None, "prefork worker exited before claiming the document"
            await asyncio.sleep(0.1)
        else:
            diagnostic = await asyncio.to_thread(log.read_text, encoding="utf-8", errors="replace")
            pytest.fail(f"prefork child did not begin parsing: {diagnostic[-2000:]}")
        children = (await asyncio.to_thread(Path(f"/proc/{worker.pid}/task/{worker.pid}/children").read_text)).split()
        assert len(children) == 1
        os.kill(int(children[0]), signal.SIGKILL)
        lease = PostgresParsingLease(session_factory.kw["bind"])
        for _ in range(100):
            async with lease.acquire(document.id) as released:
                if released:
                    break
            await asyncio.sleep(0.1)
        else:
            pytest.fail("worker's PostgreSQL lease was not released")
        async with session_factory() as session, session.begin():
            await session.execute(
                update(Document)
                .where(Document.id == document.id)
                .values(updated_at=datetime.now(UTC) - timedelta(minutes=11))
            )
        watchdog = Watchdog(
            session_factory=session_factory,
            parts=DocumentPartRepository,
            documents=DocumentRepository,
            recovery=container.part_recovery,
            dispatcher=container.task_dispatcher,
            metrics=container.metrics_collector,
            parsing_lease=lease,
            notifier=container.progress_notifier,
        )
        assert (await watchdog.tick()).failed == 1
        async with session_factory() as session:
            saved = await DocumentRepository(session).get(document.id)
            active = await DocumentRepository(session).count_active(owner.id)
        assert saved is not None and saved.error_code is DocumentErrorCode.PARSE_FAILED
        assert saved.status is DocumentStatus.FAILED and active == 0
        assert await redis.ping()
    finally:
        worker.terminate()
        try:
            await asyncio.to_thread(worker.wait, timeout=10)
        except subprocess.TimeoutExpired:
            worker.kill()
            await asyncio.to_thread(worker.wait, timeout=5)
        await container.close()
        broker.close()
        await redis.aclose()
