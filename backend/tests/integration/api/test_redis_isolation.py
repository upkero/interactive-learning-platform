"""Redis logical databases isolate rate limits from the embedding cache.

Test uses dedicated Redis databases for complete isolation:
- DB 4 (cache): embedding cache
- DB 5 (broker): Celery broker
- DB 6 (progress): progress streams
- DB 7 (rate-limit): rate limits

These DBs are allocated specifically for this test and do not overlap with
CI environment (redis://localhost:6379/0, 13, 14, 15) or production
compose.yml configuration (broker 0, progress 1, rate-limit 2, cache 3).
"""

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

# Redis URL with default host/port, DBs allocated specifically for this test
ILP_TEST_REDIS_URL = os.environ.get("ILP_TEST_REDIS_URL", "redis://localhost:6379")

# Dedicated DB indices for complete isolation
_DB_CACHE = int(os.environ.get("ILP_TEST_DB_CACHE", "4"))
_DB_BROKER = int(os.environ.get("ILP_TEST_DB_BROKER", "5"))
_DB_PROGRESS = int(os.environ.get("ILP_TEST_DB_PROGRESS", "6"))
_DB_RATE_LIMIT = int(os.environ.get("ILP_TEST_DB_RATE_LIMIT", "7"))

# CI/Production env vars to check for DB conflicts
_ENV_DB_VARS = [
    "REDIS_URL",
    "REDIS_PROGRESS_URL",
    "TEST_CELERY_BROKER_URL",
    "TEST_CELERY_REDIS_URL",
    "RATE_LIMIT_STORAGE_URI",
    "EMBEDDINGS_CACHE_REDIS_URL",
]

# Redis schemes that use logical databases
_REDIS_SCHEMES = {"redis", "rediss"}


def _client(uri: str) -> Redis:
    return Redis.from_url(uri, socket_connect_timeout=1, socket_timeout=1, retry=Retry(NoBackoff(), 0))


def _database(uri: str) -> int:
    """Extract DB index from Redis URL. Returns 0 if no DB is specified."""
    path = urlsplit(uri).path.strip("/")
    return int(path) if path else 0


def _scheme(uri: str) -> str:
    """Extract scheme from URL (e.g., 'redis' from 'redis://...')."""
    return urlsplit(uri).scheme


def _parse_db_from_env(var_name: str) -> int | None:
    """Extract DB index from environment variable URL, or None if variable not set or non-Redis scheme.

    For non-Redis schemes (memory://, sentinel://, etc.), returns None since
    these roles don't use Redis logical databases.
    """
    value = os.environ.get(var_name)
    if not value:
        return None
    scheme = _scheme(value)
    if scheme not in _REDIS_SCHEMES:
        # Non-Redis schemes don't use Redis DBs
        return None
    return _database(value)


def _check_url_validation() -> None:
    """Verify that ILP_TEST_REDIS_URL does not contain a DB number in its path."""
    scheme = _scheme(ILP_TEST_REDIS_URL)
    if scheme not in _REDIS_SCHEMES:
        return  # Non-Redis scheme, skip validation

    path = urlsplit(ILP_TEST_REDIS_URL).path.strip("/")
    if path:
        pytest.fail(
            f"ILP_TEST_REDIS_URL must not contain a DB number: {ILP_TEST_REDIS_URL}. "
            f"Use host:port only; DBs are assigned via ILP_TEST_DB_* environment variables."
        )


def _check_db_isolation() -> None:
    """Verify that test DBs don't conflict with any configured Redis DBs."""
    test_dbs = {_DB_CACHE, _DB_BROKER, _DB_PROGRESS, _DB_RATE_LIMIT}
    env_dbs: set[int] = set()

    for var_name in _ENV_DB_VARS:
        db = _parse_db_from_env(var_name)
        if db is not None:
            env_dbs.add(db)

    conflicts = test_dbs & env_dbs
    if conflicts:
        conflicting_vars = [var for var in _ENV_DB_VARS if _parse_db_from_env(var) in conflicts]
        pytest.fail(
            f"Test Redis DB indices {sorted(conflicts)} conflict with environment variables: "
            f"{conflicting_vars}. These test DBs must not overlap with CI/production DBs."
        )


def _redis_uri(db: int) -> str:
    """Build Redis URI for given DB index."""
    return f"{ILP_TEST_REDIS_URL}/{db}"


def _check_databases_are_distinct() -> None:
    """Verify that all test DB indices are distinct from each other."""
    dbs = [_DB_CACHE, _DB_BROKER, _DB_PROGRESS, _DB_RATE_LIMIT]
    if len(set(dbs)) != len(dbs):
        pytest.fail(
            f"Test DB indices must all be distinct: cache={_DB_CACHE}, broker={_DB_BROKER}, "
            f"progress={_DB_PROGRESS}, rate-limit={_DB_RATE_LIMIT}"
        )


def test_databases_are_distinct_and_isolated() -> None:
    """Verify that test DB indices 4-7 are all distinct and don't conflict with environment."""
    _check_url_validation()
    _check_databases_are_distinct()
    _check_db_isolation()


@pytest.mark.parametrize(
    ("role_b", "key_prefix_b"),
    [
        ("broker", "celery-task-meta"),
        ("progress", "grasp:progress"),
        ("rate-limit", "grasp:ratelimit"),
    ],
)
def test_cache_flush_does_not_affect_role(role_b: str, key_prefix_b: str) -> None:
    """Verify cache↔role isolation: flushdb on cache must not affect role's keys.

    Tests all three pairs around embedding-cache per D-2.3-03:
    - cache vs broker (Celery message queue)
    - cache vs progress (progress streams)
    - cache vs rate-limit (request rate limiting)

    Also verifies that flushdb on role's DB preserves cache keys.
    """
    _check_url_validation()
    _check_db_isolation()
    _check_databases_are_distinct()

    db_map = {
        "cache": _DB_CACHE,
        "broker": _DB_BROKER,
        "progress": _DB_PROGRESS,
        "rate-limit": _DB_RATE_LIMIT,
    }

    cache_client = _client(_redis_uri(db_map["cache"]))
    role_client = _client(_redis_uri(db_map[role_b]))

    try:
        try:
            cache_client.ping()
            role_client.ping()
        except RedisError as exc:
            if os.environ.get("CI"):
                pytest.fail(f"Redis required for database-isolation integration test: {exc}")
            pytest.skip("Redis unavailable for database-isolation integration test")

        suffix = uuid4().hex

        # Production cache key format per D-2.3-04: emb:{model}:{revision}:{sha256}
        cache_key = f"emb:BAAI/bge-m3:{BGE_M3_REVISION}:{suffix}"
        role_key = f"{key_prefix_b}:{suffix}"

        try:
            # Verify cache key format matches production
            assert cache_key.startswith("emb:BAAI/bge-m3:"), "cache key must use production format"
            assert BGE_M3_REVISION in cache_key, "cache key must contain model revision"

            # Write keys to both clients
            assert role_client.set(role_key, b"role-value")
            assert cache_client.set(cache_key, b"cache-value")

            # flushdb on cache should NOT affect role
            cache_client.flushdb()
            assert cache_client.get(cache_key) is None, "cache key should be removed after flushdb"
            assert role_client.get(role_key) == b"role-value", f"{role_b} key must survive flushdb on cache"

            # flushdb on role should NOT affect cache
            assert cache_client.set(cache_key, b"cache-value")
            role_client.flushdb()
            assert cache_client.get(cache_key) == b"cache-value", "cache key must survive flushdb on role"
            assert role_client.get(role_key) is None, f"{role_b} key should be removed after flushdb"
        finally:
            role_client.delete(role_key)
            cache_client.delete(cache_key)
    finally:
        role_client.close()
        cache_client.close()
