"""Shortened soft limit exercises the real prefork worker and Redis broker."""

import asyncio
import os
import subprocess
import sys
from uuid import UUID

import pytest
from celery import Celery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.bootstrap.container import ApplicationContainer
from src.app.contracts.documents.statuses import DocumentStatus, PartStatus
from src.app.models.generation_ledger import GenerationLedger
from src.app.repositories.document_part_repository import DocumentPartRepository
from src.app.repositories.document_repository import DocumentRepository
from src.app.tasks.names import PROCESS_PART_TASK

pytestmark = pytest.mark.integration


async def test_soft_limit_retries_then_refunds(
    monkeypatch: pytest.MonkeyPatch,
    session_factory: async_sessionmaker[AsyncSession],
    part_ids: tuple[UUID, UUID, UUID],
) -> None:
    broker = os.environ.get("TEST_CELERY_BROKER_URL")
    if not broker:
        pytest.skip("TEST_CELERY_BROKER_URL must point to an isolated Redis broker")
    monkeypatch.setenv("CELERY_BROKER_URL", broker)
    user_id, document_id, part_id = part_ids
    container = ApplicationContainer()
    async with session_factory() as session, session.begin():
        await container.quota_ledger.reserve(session, user_id=user_id, document_id=document_id, parts=1)
        await DocumentRepository(session).set_status(document_id, DocumentStatus.GENERATING)
    app = Celery(broker=broker)
    env = {**os.environ, "CELERY_BROKER_URL": broker, "REDIS_PROGRESS_URL": broker, "SOLVER_PIPELINE": "stub"}
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "celery",
        "-A",
        "src.worker",
        "worker",
        "-Q",
        "maintenance,parts.high,parts",
        "--concurrency=1",
        "--pool=prefork",
        "--soft-time-limit=1",
        "--time-limit=5",
        "--loglevel=WARNING",
        "--without-gossip",
        "--without-mingle",
        "--without-heartbeat",
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        await asyncio.to_thread(app.send_task, PROCESS_PART_TASK, args=[str(part_id)], queue="parts")
        part = None
        for _ in range(200):
            async with session_factory() as session:
                part = await DocumentPartRepository(session).get(part_id)
                if part is not None and part.status is PartStatus.FAILED:
                    break
            await asyncio.sleep(0.1)
        assert part is not None and part.status is PartStatus.FAILED and part.attempts == 2
        async with session_factory() as session:
            entries = (await session.scalars(select(GenerationLedger).where(GenerationLedger.op == "refund"))).all()
            assert len(entries) == 1 and entries[0].part_id == part_id
    finally:
        process.terminate()
        await asyncio.wait_for(process.wait(), timeout=15)
        app.close()
        await container.close()
