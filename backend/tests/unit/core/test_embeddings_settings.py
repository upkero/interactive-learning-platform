"""Unit tests of embedding settings (story 2.3)."""

import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

import pytest
import redis.asyncio as aioredis
from pydantic import SecretStr, ValidationError

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


def test_same_redis_database_is_rejected() -> None:
    with pytest.raises(RedisIsolationConfigurationError, match="same Redis logical database"):
        validate_redis_isolation(
            embeddings_cache_redis_url="redis://localhost:6379/3",
            rate_limit_storage_uri="redis://localhost:6379/3",
        )


def test_redis_url_variants_are_normalized_before_comparison() -> None:
    with pytest.raises(RedisIsolationConfigurationError, match="same Redis logical database"):
        validate_redis_isolation(
            embeddings_cache_redis_url="redis://LOCALHOST:6379/03",
            rate_limit_storage_uri="redis+asyncio://localhost:6379/3",
        )


def test_different_redis_database_is_allowed() -> None:
    validate_redis_isolation(
        embeddings_cache_redis_url="redis://localhost:6379/3",
        rate_limit_storage_uri="redis://localhost:6379/2",
    )


def test_memory_rate_limit_is_allowed() -> None:
    validate_redis_isolation(
        embeddings_cache_redis_url="redis://localhost:6379/3",
        rate_limit_storage_uri="memory://",
    )


@pytest.mark.parametrize(
    "rate_limit_storage_uri",
    [
        "redis://cache.example:6379/3",
        "redis://localhost:6380/3",
    ],
)
def test_different_redis_host_or_port_is_allowed(rate_limit_storage_uri: str) -> None:
    validate_redis_isolation(
        embeddings_cache_redis_url="redis://localhost:6379/3",
        rate_limit_storage_uri=rate_limit_storage_uri,
    )


@pytest.mark.parametrize(
    "rate_limit_storage_uri",
    [
        "redis://localhost:6379/2",
        "redis+asyncio://localhost:6379/2",
    ],
)
def test_redis_url_variants_with_different_database_are_allowed(rate_limit_storage_uri: str) -> None:
    validate_redis_isolation(
        embeddings_cache_redis_url="redis://localhost:6379/3",
        rate_limit_storage_uri=rate_limit_storage_uri,
    )


def test_application_startup_rejects_shared_embedding_and_rate_limit_redis_database(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["EMBEDDINGS_CACHE_REDIS_URL"] = "redis://localhost:6379/3"
    env["RATE_LIMIT_STORAGE_URI"] = "redis://localhost:6379/3"
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[3])

    result = subprocess.run(
        [sys.executable, "-c", "import src.main"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "RATE_LIMIT_STORAGE_URI" in result.stderr
    assert "EMBEDDINGS_CACHE_REDIS_URL" in result.stderr
    assert "same Redis logical database" in result.stderr


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
