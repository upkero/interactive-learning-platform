"""Exercise the event wire format and JSON logging against Redis and a worker."""

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
import redis.asyncio as redis
from celery import Celery

from src.app.contracts.progress import ProgressEventType
from src.app.core.settings.progress import ProgressSettings
from src.app.observability.progress_notifier import RedisProgressNotifier
from src.app.tasks.names import PROCESS_PART_TASK

pytestmark = pytest.mark.integration


async def test_progress_stream_json_contract(broker_url: str) -> None:
    client = redis.Redis.from_url(broker_url)
    document_id, part_id = uuid4(), uuid4()
    key = f"progress:{document_id}"
    notifier = RedisProgressNotifier(client, ProgressSettings())
    try:
        await notifier.emit(
            document_id, ProgressEventType.PART_STATUS, part_id=part_id, stage="main_pass", message="Processing"
        )
        rows = await client.xrange(key)
        assert len(rows) == 1
        event = json.loads(rows[0][1][b"data"])
        assert event["type"] == "part_status" and event["part_id"] == str(part_id)
        assert event["stage"] == "main_pass" and event["message"] == "Processing" and event["ts"]
        assert await client.ttl(key) > 0
    finally:
        await client.delete(key)
        await client.aclose()


async def test_worker_logs_skip_as_json_with_part_id(
    monkeypatch: pytest.MonkeyPatch,
    broker_url: str,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("CELERY_BROKER_URL", broker_url)
    # A missing UUID must reach the task and take the part.skip branch.
    part_id = uuid4()
    app = Celery(broker=broker_url)
    log_file = tmp_path / "worker.log"
    metrics_dir = tmp_path / "prom"
    metrics_dir.mkdir()
    with log_file.open("wb") as output:
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
            "--loglevel=INFO",
            "--without-gossip",
            "--without-mingle",
            "--without-heartbeat",
            env={
                **os.environ,
                "LOG_FORMAT": "json",
                "CELERY_BROKER_URL": broker_url,
                "PROMETHEUS_MULTIPROC_DIR": str(metrics_dir),
            },
            stdout=output,
            stderr=subprocess.STDOUT,
        )
        try:
            await asyncio.to_thread(app.send_task, PROCESS_PART_TASK, args=[str(part_id)], queue="parts")
            event = None
            for _ in range(200):
                for line in log_file.read_text(encoding="utf-8").splitlines():
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if record.get("message") == "part.skip":
                        event = record
                        break
                if event is not None:
                    break
                await asyncio.sleep(0.1)
            assert event is not None and event["part_id"] == str(part_id)
        finally:
            if process.returncode is None:
                process.terminate()
            await asyncio.wait_for(process.wait(), timeout=15)
            app.close()
