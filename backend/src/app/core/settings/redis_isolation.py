"""Fail-fast validation of Redis logical-database isolation."""

from __future__ import annotations

import posixpath
from dataclasses import dataclass
from typing import cast
from urllib.parse import parse_qsl, unquote, urlsplit

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

# Kombu's Redis transport uses these schemes for Unix-domain sockets.  The
# logical database is selected by ``virtual_host`` rather than by a path
# segment, because the path itself identifies the socket.
_KOMBU_SOCKET_SCHEMES = {
    "redis+socket",
    "rediss+socket",
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


def _normalise_unix_path(path: str) -> str:
    """Return a stable string form of a Unix-socket path."""
    if not path:
        return path
    normalised = posixpath.normpath(unquote(path))
    if normalised.startswith("/"):
        return "/" + normalised.lstrip("/")
    return normalised


def _kombu_socket_database(query: dict[str, str]) -> int:
    """Parse Kombu's socket-URL database selection."""
    virtual_host = query.get("virtual_host")
    if virtual_host is None or virtual_host in {"", "/"}:
        return 0
    if virtual_host.startswith("/"):
        virtual_host = virtual_host[1:]
    try:
        return int(virtual_host)
    except ValueError as exc:
        raise ValueError(f"Invalid value for 'virtual_host' in Redis socket URL: {virtual_host!r}") from exc


def _kombu_socket_target(url: str) -> RedisTarget:
    """Parse a Kombu Redis Unix-socket URL without connecting to Redis."""
    parsed = urlsplit(url)
    if not parsed.path:
        raise ValueError("Redis socket URL must include a socket path")

    query = dict(parse_qsl(parsed.query))
    return RedisTarget(
        database=_kombu_socket_database(query),
        unix_path=_normalise_unix_path(parsed.path),
    )


def _redis_target(url: str) -> RedisTarget | None:
    """Parse a Redis URL with redis-py or Kombu URL semantics."""
    scheme = urlsplit(url).scheme.lower()
    if scheme in _KOMBU_SOCKET_SCHEMES:
        if "://" not in url:
            return None
        return _kombu_socket_target(url)

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
        return RedisTarget(database=database, unix_path=_normalise_unix_path(unix_path))

    raw_host = parsed.get("host")
    raw_port = parsed.get("port")
    host = raw_host.casefold() if isinstance(raw_host, str) else _DEFAULT_HOST
    port = raw_port if isinstance(raw_port, int) else _DEFAULT_PORT
    return RedisTarget(database=database, host=host, port=port)


def _reject_shared_database(
    *,
    embeddings_target: RedisTarget,
    other_target: RedisTarget | None,
    other_role: str,
    other_setting: str,
) -> None:
    """Reject one role that shares the embedding cache's Redis database."""
    if other_target is None or not embeddings_target.same_database_as(other_target):
        return

    raise RedisIsolationConfigurationError(
        f"Embedding cache (EMBEDDINGS_CACHE_REDIS_URL) and {other_role} ({other_setting}) must not use "
        f"the same Redis logical database (both target {embeddings_target.label()}). "
        "Configure distinct Redis databases or separate Redis hosts."
    )


def validate_redis_isolation(
    *,
    embeddings_cache_redis_url: str,
    celery_broker_url: str,
    progress_redis_url: str,
    rate_limit_storage_uri: str,
) -> None:
    """Reject embedding-cache collisions with the broker, progress, or rate limits.

    Only roles backed by Redis can collide. A memory or other non-Redis role is
    skipped independently, so a non-Redis broker does not hide a progress or
    rate-limit collision with the embedding cache.
    """
    embeddings_target = _redis_target(embeddings_cache_redis_url)
    celery_target = _redis_target(celery_broker_url)
    progress_target = _redis_target(progress_redis_url)
    rate_limit_target = _redis_target(rate_limit_storage_uri)

    if embeddings_target is None:
        return

    _reject_shared_database(
        embeddings_target=embeddings_target,
        other_target=celery_target,
        other_role="Celery broker",
        other_setting="CELERY_BROKER_URL",
    )
    _reject_shared_database(
        embeddings_target=embeddings_target,
        other_target=progress_target,
        other_role="progress streams",
        other_setting="REDIS_PROGRESS_URL",
    )
    _reject_shared_database(
        embeddings_target=embeddings_target,
        other_target=rate_limit_target,
        other_role="rate-limit counters",
        other_setting="RATE_LIMIT_STORAGE_URI",
    )


__all__ = ["RedisTarget", "validate_redis_isolation"]
