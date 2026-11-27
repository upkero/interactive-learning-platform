"""Unit tests of embedding settings (story 2.3)."""

import pytest
from pydantic import SecretStr, ValidationError

from src.app.core.settings.embeddings import EmbeddingsSettings


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "EMBEDDINGS_PROVIDER",
        "EMBEDDINGS_DEVICE",
        "EMBEDDINGS_BATCH_SIZE",
        "EMBEDDINGS_CACHE_TTL_DAYS",
        "EMBEDDINGS_CACHE_REDIS_URL",
        "VOYAGE_API_KEY",
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
    assert settings.cache_redis_url == "redis://localhost:6379/2"
    assert settings.voyage_api_key is None


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
