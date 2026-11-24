"""Smoke-test a real unprivileged prefork worker against isolated Redis."""

import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest
from celery import Celery

pytestmark = pytest.mark.integration


def test_prefork_worker_aggregates_two_processes(tmp_path: Path) -> None:
    redis_url = os.environ.get("TEST_CELERY_REDIS_URL")
    if not redis_url:
        pytest.skip("TEST_CELERY_REDIS_URL must point to an isolated Redis instance")
    assert os.getuid() != 0, "run the worker smoke test as an unprivileged user"
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = {
        **os.environ,
        "PROMETHEUS_MULTIPROC_DIR": str(tmp_path),
        "OBSERVABILITY_WORKER_METRICS_PORT": str(port),
    }
    worker = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "celery",
            "-A",
            "tests.support.observability_worker",
            "worker",
            "--pool=prefork",
            "--concurrency=2",
            "--loglevel=WARNING",
            "--without-gossip",
            "--without-mingle",
            "--without-heartbeat",
        ],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    app = Celery("observability_test_client", broker=redis_url, backend=redis_url)
    try:
        url = f"http://127.0.0.1:{port}/metrics"
        for _ in range(150):
            if worker.poll() is not None:
                pytest.fail(f"worker exited with code {worker.returncode}")
            try:
                urllib.request.urlopen(url, timeout=1).close()
                break
            except (OSError, urllib.error.URLError):
                time.sleep(0.1)
        else:
            pytest.fail("worker metrics server did not start")
        results = [app.send_task("observability.smoke") for _ in range(2)]
        pids = {result.get(timeout=30) for result in results}
        assert len(pids) == 2
        for _ in range(100):
            with urllib.request.urlopen(url, timeout=1) as response:
                metrics = response.read().decode()
            if 'celery_tasks_total{state="success",task="observability.smoke"} 2.0' in metrics:
                break
            time.sleep(0.1)
        else:
            pytest.fail("metrics did not contain both completed tasks")
    finally:
        worker.terminate()
        try:
            worker.wait(timeout=15)
        except subprocess.TimeoutExpired:
            worker.kill()
            worker.wait(timeout=5)
        app.close()
