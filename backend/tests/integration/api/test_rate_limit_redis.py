"""Real Redis counters shared by independent application processes."""

import json
import os
import socket
import subprocess
import sys
from uuid import uuid4

import pytest
from redis import Redis
from redis.backoff import NoBackoff
from redis.exceptions import RedisError
from redis.retry import Retry

pytestmark = pytest.mark.integration

_WORKER = r"""
import json, sys
from fastapi.testclient import TestClient
from src.app.api.v1.dependencies.auth import get_auth_service
from src.app.exceptions.auth import InvalidCredentialsError
from src.main import create_app

class FakeAuth:
    async def login(self, *, email, password):
        raise InvalidCredentialsError()

app = create_app()
app.dependency_overrides[get_auth_service] = lambda: FakeAuth()
with TestClient(app) as client:
    statuses = [client.post('/api/v1/auth/login', headers={'X-Real-IP': sys.argv[2]},
        json={'email': 'nobody@example.com', 'password': 'not-the-password'}).status_code
        for _ in range(int(sys.argv[1]))]
print(json.dumps(statuses))
"""


def _worker(uri: str, count: int, ip: str) -> list[int]:
    env = {**os.environ, "RATE_LIMIT_STORAGE_URI": uri}
    result = subprocess.run(
        [sys.executable, "-c", _WORKER, str(count), ip],
        env=env,
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    return json.loads(result.stdout.splitlines()[-1])  # type: ignore[no-any-return]


def test_two_workers_share_redis_rate_limit() -> None:
    uri = os.environ.get("TEST_RATE_LIMIT_REDIS_URI", "redis://localhost:6379/2")
    redis = Redis.from_url(uri, socket_connect_timeout=1, socket_timeout=1, retry=Retry(NoBackoff(), 0))
    try:
        redis.ping()
    except RedisError as exc:
        if os.environ.get("CI"):
            pytest.fail(f"Redis required for shared counter integration test: {exc}")
        pytest.skip("Redis unavailable for shared counter integration test")
    finally:
        redis.close()
    value = uuid4().int
    ip = f"198.18.{value % 256}.{(value // 256) % 256}"
    assert _worker(uri, 10, ip) == [401] * 10
    assert _worker(uri, 1, ip) == [429]


def test_unavailable_redis_falls_back_to_memory() -> None:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        assert _worker(f"redis://127.0.0.1:{port}/2", 1, str(uuid4())) == [401]
