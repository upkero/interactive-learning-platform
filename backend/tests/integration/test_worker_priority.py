"""Requires a dedicated Redis broker; never clears any existing database."""

import os
import subprocess
import sys
import time
from typing import cast
from uuid import uuid4

import pytest
import redis
from celery import Celery

pytestmark = pytest.mark.integration


def test_worker_consumes_high_priority_before_normal(monkeypatch: pytest.MonkeyPatch) -> None:
    broker = os.environ.get("TEST_CELERY_BROKER_URL")
    if not broker:
        if os.environ.get("CI"):
            pytest.fail("TEST_CELERY_BROKER_URL is required in CI")
        pytest.skip("TEST_CELERY_BROKER_URL must point to an isolated Redis broker")
    monkeypatch.setenv("CELERY_BROKER_URL", broker)
    key = f"priority-test-{uuid4()}"
    client = redis.Redis.from_url(broker)
    app = Celery(broker=broker)
    for _ in range(20):
        app.send_task("tests.record_priority", args=[key, "normal"], queue="parts")
    app.send_task("tests.record_priority", args=[key, "high"], queue="parts.high")
    env = {**os.environ, "CELERY_BROKER_URL": broker}
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "celery",
            "-A",
            "tests.support.priority_worker",
            "worker",
            "-Q",
            "maintenance,parts.high,parts",
            "--concurrency=1",
            "--pool=solo",
            "--loglevel=WARNING",
            "--without-gossip",
            "--without-mingle",
            "--without-heartbeat",
        ],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 20
        while cast(int, client.llen(key)) < 21 and time.monotonic() < deadline:
            assert process.poll() is None, "worker exited before consuming tasks"
            time.sleep(0.1)
        assert client.lrange(key, 0, -1) == [b"high", *([b"normal"] * 20)]
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        client.delete(key)
        client.close()
        app.close()
