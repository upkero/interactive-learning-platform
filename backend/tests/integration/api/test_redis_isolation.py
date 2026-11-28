"""Redis logical databases isolate rate limits from the embedding cache."""

import os
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
from redis import Redis
from redis.backoff import NoBackoff
from redis.exceptions import RedisError
from redis.retry import Retry

from src.app.core.settings.embeddings import BGE_M3_REVISION

pytestmark = pytest.mark.integration

_RATE_LIMIT_URI = "redis://localhost:6379/12"
_EMBEDDINGS_CACHE_URI = "redis://localhost:6379/13"


def _client(uri: str) -> Redis:
    return Redis.from_url(uri, socket_connect_timeout=1, socket_timeout=1, retry=Retry(NoBackoff(), 0))


def _database(uri: str) -> int:
    path = urlsplit(uri).path.strip("/")
    return int(path) if path else 0


def test_flushing_embedding_cache_does_not_remove_rate_limit_keys() -> None:
    rate_limits = _client(_RATE_LIMIT_URI)
    cache = _client(_EMBEDDINGS_CACHE_URI)
    try:
        try:
            rate_limits.ping()
            cache.ping()
        except RedisError as exc:
            if os.environ.get("CI"):
                pytest.fail(f"Redis required for database-isolation integration test: {exc}")
            pytest.skip("Redis unavailable for database-isolation integration test")

        assert _database(_RATE_LIMIT_URI) != _database(_EMBEDDINGS_CACHE_URI)

        suffix = uuid4().hex
        rate_limit_key = f"grasp:ratelimit:{suffix}"
        cache_key = f"emb:BAAI/bge-m3:{BGE_M3_REVISION}:{suffix}"
        try:
            assert rate_limits.set(rate_limit_key, "counter")
            assert cache.set(cache_key, "vector")

            cache.flushdb()

            assert cache.get(cache_key) is None
            assert rate_limits.get(rate_limit_key) == b"counter"

            assert cache.set(cache_key, "vector")
            rate_limits.flushdb()

            assert rate_limits.get(rate_limit_key) is None
            assert cache.get(cache_key) == b"vector"
        finally:
            rate_limits.delete(rate_limit_key)
            cache.delete(cache_key)
    finally:
        rate_limits.close()
        cache.close()
