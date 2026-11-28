"""Unit tests of embedder construction and process-wide caching (story 2.3)."""

import sys
from collections.abc import Iterator, Sequence
from threading import get_ident
from types import ModuleType

import pytest
from pydantic import SecretStr

from src.app.bootstrap.container import ApplicationContainer
from src.app.core.settings.embeddings import BGE_M3_REVISION, EmbeddingsSettings
from src.app.embeddings import factory
from src.app.embeddings.bge_m3 import BGE_M3_DIMENSION, BGE_M3_MODEL
from src.app.embeddings.voyage import VOYAGE_DIMENSION, VOYAGE_MODEL
from src.app.exceptions.embeddings import EmbeddingConfigurationError
from tests.support.fakes.cache.redis import FakeRedis


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
        def __init__(self, *, device: str, revision: str) -> None:
            captured["device"] = device
            captured["revision"] = revision

    monkeypatch.setattr(factory, "BgeM3Embedder", FakeBge)

    result = factory.create_embedder(_settings(provider="bge_m3", device="cuda", revision=BGE_M3_REVISION))

    assert isinstance(result, FakeBge)
    assert captured == {"device": "cuda", "revision": BGE_M3_REVISION}


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


def test_get_embedder_process_cache_separates_revisions(monkeypatch: pytest.MonkeyPatch) -> None:
    created: list[str] = []

    def fake_create(settings: EmbeddingsSettings) -> FakeEmbedder:
        created.append(settings.revision)
        return FakeEmbedder()

    monkeypatch.setattr(factory, "create_embedder", fake_create)
    revision_a = "revision-a"
    revision_b = "revision-b"

    first = factory.get_embedder(_settings(revision=revision_a))
    same_revision = factory.get_embedder(_settings(revision=revision_a))
    other_revision = factory.get_embedder(_settings(revision=revision_b))

    assert first is same_revision
    assert first is not other_revision
    assert created == [revision_a, revision_b]


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


def test_lazy_bge_factory_loads_real_wrapper_on_first_embed_without_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeSentenceTransformer:
        def __init__(self, model_name: str, *, device: str, revision: str) -> None:
            captured.update(model=model_name, device=device, revision=revision)

        def encode(self, texts: list[str], *, normalize_embeddings: bool) -> list[list[float]]:
            captured["texts"] = texts
            captured["normalize"] = normalize_embeddings
            return [[1.0, 0.0] for _ in texts]

    module = ModuleType("sentence_transformers")
    module.SentenceTransformer = FakeSentenceTransformer  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sentence_transformers", module)
    lazy = factory.LazyEmbedder(_settings(provider="bge_m3", revision=BGE_M3_REVISION))

    assert captured == {}

    vectors = lazy.embed(["query"])

    assert vectors == [[1.0, 0.0]]
    assert captured == {
        "model": BGE_M3_MODEL,
        "device": "cpu",
        "revision": BGE_M3_REVISION,
        "texts": ["query"],
        "normalize": True,
    }


async def test_container_loads_and_encodes_off_event_loop_on_first_cache_miss(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, int]] = []

    class RecordingBge(FakeEmbedder):
        dimension = BGE_M3_DIMENSION

        def __init__(self, *, device: str, revision: str) -> None:
            assert device == "cpu"
            assert revision == BGE_M3_REVISION
            calls.append(("load", get_ident()))

        def embed(self, texts: Sequence[str]) -> list[list[float]]:
            calls.append(("embed", get_ident()))
            return super().embed(texts)

    monkeypatch.setattr(factory, "BgeM3Embedder", RecordingBge)
    container = ApplicationContainer()
    monkeypatch.setattr(container, "embeddings_settings", _settings(provider="bge_m3", device="cpu"))
    monkeypatch.setattr(container, "embeddings_redis", FakeRedis())
    loop_thread = get_ident()

    try:
        service = container.embedding_service
        assert calls == []
        await service.embed(["query"])
        await service.embed(["query"])
        await service.embed(["another query"])
    finally:
        await container.close()

    assert [action for action, _ in calls] == ["load", "embed", "embed"]
    assert all(thread != loop_thread for _, thread in calls)


async def test_two_container_providers_keep_models_and_redis_keys_separate(monkeypatch: pytest.MonkeyPatch) -> None:
    cache = FakeRedis()
    local_settings = _settings(provider="bge_m3", device="cpu")
    voyage_settings = _settings(provider="voyage", voyage_api_key=SecretStr("fake-api-key"))
    created: list[str] = []

    class DifferentVectors(FakeEmbedder):
        def __init__(self, settings: EmbeddingsSettings) -> None:
            self.dimension = BGE_M3_DIMENSION if settings.provider == "bge_m3" else VOYAGE_DIMENSION
            self.value = 1.0 if settings.provider == "bge_m3" else 2.0

        def embed(self, texts: Sequence[str]) -> list[list[float]]:
            return [[self.value] * self.dimension for _ in texts]

    def fake_create(settings: EmbeddingsSettings) -> DifferentVectors:
        created.append(settings.provider)
        return DifferentVectors(settings)

    monkeypatch.setattr(factory, "create_embedder", fake_create)
    for settings, value in ((local_settings, 1.0), (voyage_settings, 2.0), (local_settings, 1.0)):
        container = ApplicationContainer()
        monkeypatch.setattr(container, "embeddings_settings", settings)
        monkeypatch.setattr(container, "embeddings_redis", cache)
        try:
            (vector,) = await container.embedding_service.embed(["one shared query"])
            assert vector[0] == value
        finally:
            await container.close()

    assert created == ["bge_m3", "voyage"]
    assert {key.rsplit(":", 1)[0] for key in cache.store} == {
        f"emb:{BGE_M3_MODEL}:{BGE_M3_REVISION}",
        f"emb:{VOYAGE_MODEL}:{BGE_M3_REVISION}",
    }
