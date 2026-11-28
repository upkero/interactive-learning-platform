"""Unit tests of embedding settings (story 2.3)."""

import os
import socket
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

import pytest
import redis.asyncio as aioredis
from pydantic import SecretStr, ValidationError
from redis.connection import Connection as RedisConnection

from src.app.bootstrap import container as container_module
from src.app.bootstrap.container import ApplicationContainer
from src.app.core.settings.celery import CelerySettings
from src.app.core.settings.embeddings import EmbeddingsSettings
from src.app.core.settings.progress import ProgressSettings
from src.app.core.settings.rate_limit import RateLimitSettings
from src.app.core.settings.redis_isolation import validate_redis_isolation
from src.app.exceptions.redis import RedisIsolationConfigurationError


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "EMBEDDINGS_PROVIDER",
        "EMBEDDINGS_DEVICE",
        "EMBEDDINGS_REVISION",
        "EMBEDDINGS_BATCH_SIZE",
        "EMBEDDINGS_CACHE_TTL_DAYS",
        "EMBEDDINGS_CACHE_REDIS_URL",
        "VOYAGE_API_KEY",
        "CELERY_BROKER_URL",
        "REDIS_PROGRESS_URL",
        "RATE_LIMIT_STORAGE_URI",
    ):
        monkeypatch.delenv(name, raising=False)


def _settings() -> EmbeddingsSettings:
    return EmbeddingsSettings(_env_file=None)


def test_defaults_select_the_local_model_and_dedicated_cache_database() -> None:
    settings = _settings()

    assert settings.provider == "bge_m3"
    assert settings.device == "cpu"
    assert settings.revision == "5617a9f61b028005a4858fdac845db406aefb181"
    assert settings.batch_size == 32
    assert settings.cache_ttl_days == 30
    assert settings.cache_ttl_seconds == 30 * 24 * 3600
    assert settings.cache_redis_url == "redis://localhost:6379/3"
    assert settings.voyage_api_key is None


def _redis_database(url: str) -> int:
    path = urlsplit(url).path.strip("/")
    return int(path) if path else 0


def test_redis_roles_use_distinct_logical_databases() -> None:
    """A cache flush must not reach the broker, progress, or rate-limit keys."""
    urls = (
        CelerySettings(_env_file=None).broker_url,
        str(ProgressSettings(_env_file=None).url),
        RateLimitSettings(storage_uri="redis://localhost:6379/2").storage_uri,
        _settings().cache_redis_url,
    )

    databases = [_redis_database(url) for url in urls]

    assert databases == [0, 1, 2, 3]
    assert len(set(databases)) == len(databases)


def _validate_isolation(
    *,
    embeddings_cache_redis_url: str = "redis://localhost:6379/3",
    celery_broker_url: str = "redis://localhost:6379/0",
    progress_redis_url: str = "redis://localhost:6379/1",
    rate_limit_storage_uri: str = "redis://localhost:6379/2",
) -> None:
    validate_redis_isolation(
        embeddings_cache_redis_url=embeddings_cache_redis_url,
        celery_broker_url=celery_broker_url,
        progress_redis_url=progress_redis_url,
        rate_limit_storage_uri=rate_limit_storage_uri,
    )


def test_embedding_cache_collision_with_celery_broker_is_rejected() -> None:
    with pytest.raises(RedisIsolationConfigurationError, match="same Redis logical database") as error:
        _validate_isolation(
            celery_broker_url="redis://localhost:6379/3",
            rate_limit_storage_uri="memory://",
        )

    message = str(error.value)
    assert "Embedding cache (EMBEDDINGS_CACHE_REDIS_URL)" in message
    assert "Celery broker (CELERY_BROKER_URL)" in message
    assert "localhost:6379/3" in message


def test_embedding_cache_collision_with_progress_is_rejected() -> None:
    with pytest.raises(RedisIsolationConfigurationError, match="same Redis logical database") as error:
        _validate_isolation(
            progress_redis_url="redis://localhost:6379/3",
            rate_limit_storage_uri="memory://",
        )

    message = str(error.value)
    assert "Embedding cache (EMBEDDINGS_CACHE_REDIS_URL)" in message
    assert "progress streams (REDIS_PROGRESS_URL)" in message
    assert "localhost:6379/3" in message


def test_embedding_cache_collision_with_rate_limit_is_rejected() -> None:
    with pytest.raises(RedisIsolationConfigurationError, match="same Redis logical database") as error:
        _validate_isolation(rate_limit_storage_uri="redis://localhost:6379/3")

    message = str(error.value)
    assert "Embedding cache (EMBEDDINGS_CACHE_REDIS_URL)" in message
    assert "rate-limit counters (RATE_LIMIT_STORAGE_URI)" in message
    assert "localhost:6379/3" in message


@pytest.mark.parametrize(
    ("role", "other_url"),
    [
        ("broker", "redis://localhost:6379/4"),
        ("progress", "redis://localhost:6379/4"),
        ("rate", "redis://localhost:6379/4"),
        ("broker", "redis://broker.example:6379/3"),
        ("progress", "redis://progress.example:6379/3"),
        ("rate", "redis://rate.example:6379/3"),
        ("broker", "redis://localhost:6380/3"),
        ("progress", "redis://localhost:6380/3"),
        ("rate", "redis://localhost:6380/3"),
    ],
)
def test_different_database_host_or_port_is_allowed(role: str, other_url: str) -> None:
    if role == "broker":
        _validate_isolation(celery_broker_url=other_url)
    elif role == "progress":
        _validate_isolation(progress_redis_url=other_url)
    else:
        assert role == "rate"
        _validate_isolation(rate_limit_storage_uri=other_url)


def test_memory_rate_limit_with_isolated_broker_and_progress_is_allowed() -> None:
    _validate_isolation(rate_limit_storage_uri="memory://")


def test_non_redis_broker_is_allowed() -> None:
    _validate_isolation(celery_broker_url="memory://")


def test_non_redis_progress_is_allowed() -> None:
    _validate_isolation(progress_redis_url="memory://")


def test_pairs_not_involving_embedding_cache_are_not_checked() -> None:
    _validate_isolation(
        celery_broker_url="redis://localhost:6379/0",
        progress_redis_url="redis://localhost:6379/0",
        rate_limit_storage_uri="redis://localhost:6379/0",
    )


def test_redis_url_variants_are_normalized_before_comparison() -> None:
    with pytest.raises(RedisIsolationConfigurationError, match="same Redis logical database"):
        _validate_isolation(
            embeddings_cache_redis_url="redis://LOCALHOST:6379/03",
            rate_limit_storage_uri="redis+asyncio://localhost:6379/3",
        )


@pytest.mark.parametrize(
    "rate_limit_storage_uri",
    [
        "redis://localhost:6379/2",
        "redis+asyncio://localhost:6379/2",
    ],
)
def test_redis_url_variants_with_different_database_are_allowed(rate_limit_storage_uri: str) -> None:
    _validate_isolation(rate_limit_storage_uri=rate_limit_storage_uri)


@pytest.mark.parametrize(
    ("embeddings_cache_redis_url", "rate_limit_storage_uri"),
    [
        ("redis://host:6379?db=3", "redis://host:6379/3"),
        ("redis+unix:///path.sock?db=3", "unix:///path.sock?db=3"),
    ],
)
def test_equivalent_redis_url_forms_collide(
    embeddings_cache_redis_url: str,
    rate_limit_storage_uri: str,
) -> None:
    with pytest.raises(RedisIsolationConfigurationError, match="same Redis logical database"):
        _validate_isolation(
            embeddings_cache_redis_url=embeddings_cache_redis_url,
            rate_limit_storage_uri=rate_limit_storage_uri,
        )


@pytest.mark.parametrize(
    ("embeddings_cache_redis_url", "rate_limit_storage_uri"),
    [
        ("redis://host:6379?db=3", "redis://host:6379/2"),
        ("redis+unix:///path.sock?db=3", "unix:///path.sock?db=2"),
    ],
)
def test_different_logical_databases_in_equivalent_url_forms_are_allowed(
    embeddings_cache_redis_url: str,
    rate_limit_storage_uri: str,
) -> None:
    _validate_isolation(
        embeddings_cache_redis_url=embeddings_cache_redis_url,
        rate_limit_storage_uri=rate_limit_storage_uri,
    )


def test_malformed_cache_redis_uri_fails_fast_without_false_collision() -> None:
    with pytest.raises(ValueError, match="Invalid value for 'db'") as error:
        _validate_isolation(embeddings_cache_redis_url="redis://host:6379?db=not-a-number")

    assert not isinstance(error.value, RedisIsolationConfigurationError)


def test_malformed_broker_redis_uri_fails_fast_without_false_collision() -> None:
    with pytest.raises(ValueError, match="Invalid value for 'db'") as error:
        _validate_isolation(celery_broker_url="redis://host:6379?db=not-a-number")

    assert not isinstance(error.value, RedisIsolationConfigurationError)


def test_non_redis_rate_limit_uri_is_not_reported_as_redis_collision() -> None:
    _validate_isolation(rate_limit_storage_uri="memcached://cache:11211")


def test_collision_message_does_not_expose_credentials() -> None:
    with pytest.raises(RedisIsolationConfigurationError) as error:
        _validate_isolation(celery_broker_url="redis://cache-user:cache-password@localhost:6379/3")

    message = str(error.value)
    assert "localhost:6379/3" in message
    assert "cache-user" not in message
    assert "cache-password" not in message


def test_redis_url_parser_does_not_connect_or_resolve_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Redis URL parsing must not perform network or DNS operations")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(RedisConnection, "connect", forbidden)
    monkeypatch.setattr(RedisConnection, "_connect", forbidden)

    with pytest.raises(RedisIsolationConfigurationError, match="same Redis logical database"):
        _validate_isolation(
            embeddings_cache_redis_url="redis://does-not-resolve.invalid:6379?db=3",
            rate_limit_storage_uri="redis://does-not-resolve.invalid:6379/3",
        )


def _hermetic_subprocess_env(tmp_path: Path, **overrides: str) -> dict[str, str]:
    env = {
        "APP_ENVIRONMENT": "test",
        "AUTH_JWT_SECRET": "test-secret-key-must-be-at-least-32-chars-long",
        "RATE_LIMIT_STORAGE_URI": "redis://localhost:6379/2",
        "PYTHONPATH": str(Path(__file__).resolve().parents[3]),
    }
    # Keep the subprocess configuration explicit. Only Windows loader variables
    # are inherited; application settings cannot leak from the developer's shell.
    for name in ("SYSTEMROOT", "WINDIR"):
        value = os.environ.get(name)
        if value is not None:
            env[name] = value
    env.update(overrides)
    return env


@pytest.mark.parametrize("module", ["src.main", "src.worker"])
def test_process_import_with_default_redis_roles_succeeds(module: str, tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        cwd=tmp_path,
        env=_hermetic_subprocess_env(tmp_path),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    ("module", "collision_env", "expected_role"),
    [
        ("src.main", {"CELERY_BROKER_URL": "redis://localhost:6379/3"}, "Celery broker (CELERY_BROKER_URL)"),
        ("src.main", {"REDIS_PROGRESS_URL": "redis://localhost:6379/3"}, "progress streams (REDIS_PROGRESS_URL)"),
        ("src.worker", {"CELERY_BROKER_URL": "redis://localhost:6379/3"}, "Celery broker (CELERY_BROKER_URL)"),
        ("src.worker", {"REDIS_PROGRESS_URL": "redis://localhost:6379/3"}, "progress streams (REDIS_PROGRESS_URL)"),
    ],
)
def test_process_import_rejects_embedding_cache_collision(
    module: str,
    collision_env: dict[str, str],
    expected_role: str,
    tmp_path: Path,
) -> None:
    result = subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        cwd=tmp_path,
        env=_hermetic_subprocess_env(tmp_path, **collision_env),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "RedisIsolationConfigurationError:" in result.stderr
    assert "Embedding cache (EMBEDDINGS_CACHE_REDIS_URL)" in result.stderr
    assert expected_role in result.stderr
    assert "localhost:6379/3" in result.stderr
    assert "same Redis logical database" in result.stderr
    assert "AUTH_JWT_SECRET" not in result.stderr
    assert "jwt_secret" not in result.stderr


def test_container_builds_embedding_cache_client_from_dedicated_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict[str, object]]] = []
    client = object()

    def from_url(url: str, **kwargs: object) -> object:
        calls.append((url, kwargs))
        return client

    settings = EmbeddingsSettings(cache_redis_url="redis://cache.example:6379/13", _env_file=None)
    monkeypatch.setattr(container_module, "get_embeddings_settings", lambda: settings)
    monkeypatch.setattr(aioredis.Redis, "from_url", staticmethod(from_url))

    assert ApplicationContainer().embeddings_redis is client
    assert calls == [("redis://cache.example:6379/13", {})]


def test_environment_overrides_provider_and_voyage_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EMBEDDINGS_PROVIDER", "voyage")
    monkeypatch.setenv("VOYAGE_API_KEY", "secret")

    settings = _settings()

    assert settings.provider == "voyage"
    assert isinstance(settings.voyage_api_key, SecretStr)
    assert settings.voyage_api_key.get_secret_value() == "secret"


def test_environment_overrides_model_revision(monkeypatch: pytest.MonkeyPatch) -> None:
    revision = "0123456789abcdef0123456789abcdef01234567"
    monkeypatch.setenv("EMBEDDINGS_REVISION", revision)

    settings = _settings()

    assert settings.revision == revision


def test_voyage_requires_a_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EMBEDDINGS_PROVIDER", "voyage")

    with pytest.raises(ValidationError):
        _settings()


def test_empty_voyage_key_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EMBEDDINGS_PROVIDER", "voyage")
    monkeypatch.setenv("VOYAGE_API_KEY", "")

    with pytest.raises(ValidationError):
        _settings()


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("EMBEDDINGS_BATCH_SIZE", "0"),
        ("EMBEDDINGS_CACHE_TTL_DAYS", "0"),
    ],
)
def test_positive_bounds(monkeypatch: pytest.MonkeyPatch, name: str, value: str) -> None:
    monkeypatch.setenv(name, value)

    with pytest.raises(ValidationError):
        _settings()
