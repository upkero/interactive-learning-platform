"""Fail-fast validation of Redis logical-database isolation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast
from urllib.parse import urlsplit

from redis import Redis

from src.app.exceptions.redis import RedisIsolationConfigurationError

_DEFAULT_HOST = "localhost"
_DEFAULT_PORT = 6379

# Normalise Redis URL spellings before delegating host/port/database parsing
# to redis-py. The asyncio aliases identify the same Redis endpoint; limits
# likewise rewrites its ``redis+unix`` scheme before calling redis-py.
_CANONICAL_SCHEMES = {
    "redis": "redis",
    "rediss": "rediss",
    "redis+asyncio": "redis",
    "async+redis": "redis",
    "async+rediss": "rediss",
    "unix": "unix",
    "redis+unix": "unix",
    "async+redis+unix": "unix",
}


@dataclass(frozen=True)
class RedisTarget:
    """The Redis server and logical database selected by a URL."""

    database: int
    host: str | None = None
    port: int | None = None
    unix_path: str | None = None

    def same_database_as(self, other: RedisTarget) -> bool:
        """Return whether two URLs select the same server and logical DB."""
        if (self.unix_path is None) != (other.unix_path is None):
            return False
        if self.unix_path is not None and other.unix_path is not None:
            return self.unix_path == other.unix_path and self.database == other.database
        return self.host == other.host and self.port == other.port and self.database == other.database

    def label(self) -> str:
        """Return a credential-free description for configuration errors."""
        if self.unix_path is not None:
            return f"unix:{self.unix_path}/{self.database}"
        host = self.host or _DEFAULT_HOST
        display_host = f"[{host}]" if ":" in host else host
        return f"{display_host}:{self.port or _DEFAULT_PORT}/{self.database}"


def _canonical_redis_url(url: str) -> str | None:
    """Return a URL accepted by redis-py, or None for a non-Redis backend."""
    scheme = urlsplit(url).scheme.lower()
    canonical_scheme = _CANONICAL_SCHEMES.get(scheme)
    if canonical_scheme is None:
        return None
    _, separator, suffix = url.partition("://")
    if not separator:
        return None
    return f"{canonical_scheme}://{suffix}"


def _redis_target(url: str) -> RedisTarget | None:
    """Parse a Redis URL with redis-py's URL semantics."""
    canonical_url = _canonical_redis_url(url)
    if canonical_url is None:
        return None

    client = Redis.from_url(canonical_url)
    try:
        parsed = cast(dict[str, object], client.connection_pool.connection_kwargs)
    finally:
        client.close()
    raw_database = parsed.get("db", 0)
    database = raw_database if isinstance(raw_database, int) else 0

    if canonical_url.startswith("unix://"):
        raw_path = parsed.get("path")
        unix_path = raw_path if isinstance(raw_path, str) else ""
        return RedisTarget(database=database, unix_path=unix_path)

    raw_host = parsed.get("host")
    raw_port = parsed.get("port")
    host = raw_host.casefold() if isinstance(raw_host, str) else _DEFAULT_HOST
    port = raw_port if isinstance(raw_port, int) else _DEFAULT_PORT
    return RedisTarget(database=database, host=host, port=port)


def validate_redis_isolation(
    *,
    embeddings_cache_redis_url: str,
    rate_limit_storage_uri: str,
) -> None:
    """Reject a shared Redis logical database for rate limits and embeddings.

    Memory-backed rate limits and separate Redis servers cannot collide with
    the embedding cache, so only two parseable Redis targets are compared.
    """
    if urlsplit(rate_limit_storage_uri).scheme.lower() == "memory":
        return

    embeddings_target = _redis_target(embeddings_cache_redis_url)
    rate_limit_target = _redis_target(rate_limit_storage_uri)
    if embeddings_target is None or rate_limit_target is None:
        return
    if not embeddings_target.same_database_as(rate_limit_target):
        return

    raise RedisIsolationConfigurationError(
        "RATE_LIMIT_STORAGE_URI and EMBEDDINGS_CACHE_REDIS_URL must not use the same Redis "
        f"logical database (both target {embeddings_target.label()}). "
        "Configure distinct Redis databases or separate Redis hosts."
    )


__all__ = ["RedisTarget", "validate_redis_isolation"]
