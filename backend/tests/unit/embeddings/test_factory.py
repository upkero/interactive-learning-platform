"""Unit tests of embedder construction and process-wide caching (story 2.3)."""

from collections.abc import Iterator, Sequence

import pytest
from pydantic import SecretStr

from src.app.core.settings.embeddings import EmbeddingsSettings
from src.app.embeddings import factory
from src.app.exceptions.embeddings import EmbeddingConfigurationError


class FakeEmbedder:
    model_name = "fake"
    dimension = 4

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [[0.0] * self.dimension for _ in texts]


@pytest.fixture(autouse=True)
def _reset_process_cache() -> Iterator[None]:
    factory.reset_embedder()
    yield
    factory.reset_embedder()


def _settings(**overrides: object) -> EmbeddingsSettings:
    return EmbeddingsSettings(_env_file=None, **overrides)  # type: ignore[arg-type]


def test_bge_provider_passes_device(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str] = {}

    class FakeBge:
        def __init__(self, *, device: str) -> None:
            captured["device"] = device

    monkeypatch.setattr(factory, "BgeM3Embedder", FakeBge)

    result = factory.create_embedder(_settings(provider="bge_m3", device="cuda"))

    assert isinstance(result, FakeBge)
    assert captured == {"device": "cuda"}


def test_voyage_provider_passes_secret_key(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, SecretStr] = {}

    class FakeVoyage:
        def __init__(self, *, api_key: SecretStr) -> None:
            captured["api_key"] = api_key

    monkeypatch.setattr(factory, "VoyageEmbedder", FakeVoyage)
    settings = _settings(provider="voyage", voyage_api_key=SecretStr("secret"))

    result = factory.create_embedder(settings)

    assert isinstance(result, FakeVoyage)
    assert captured["api_key"].get_secret_value() == "secret"


def test_voyage_without_key_is_a_configuration_error() -> None:
    settings = EmbeddingsSettings.model_construct(provider="voyage", voyage_api_key=None)

    with pytest.raises(EmbeddingConfigurationError):
        factory.create_embedder(settings)


def test_get_embedder_caches_one_instance_per_process(monkeypatch: pytest.MonkeyPatch) -> None:
    created: list[FakeEmbedder] = []

    def fake_create(settings: EmbeddingsSettings) -> FakeEmbedder:
        del settings
        embedder = FakeEmbedder()
        created.append(embedder)
        return embedder

    monkeypatch.setattr(factory, "create_embedder", fake_create)
    settings = _settings()

    first = factory.get_embedder(settings)
    second = factory.get_embedder(settings)

    assert first is second
    assert len(created) == 1


def test_reset_embedder_creates_a_fresh_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    created: list[FakeEmbedder] = []

    def fake_create(settings: EmbeddingsSettings) -> FakeEmbedder:
        del settings
        embedder = FakeEmbedder()
        created.append(embedder)
        return embedder

    monkeypatch.setattr(factory, "create_embedder", fake_create)
    settings = _settings()

    first = factory.get_embedder(settings)
    factory.reset_embedder()
    second = factory.get_embedder(settings)

    assert first is not second
    assert len(created) == 2
