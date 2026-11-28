"""Unit tests of the model wrappers (story 2.3).

The real libraries are optional extras, so the tests replace the imported
module with a small fake. This keeps the wrapper contract (normalisation,
dimension, input type) covered without downloading weights.
"""

import sys
from types import ModuleType
from typing import Any, ClassVar

import pytest
from pydantic import SecretStr

from src.app.core.settings.embeddings import BGE_M3_REVISION
from src.app.embeddings import bge_m3
from src.app.embeddings.bge_m3 import BGE_M3_MODEL, BgeM3Embedder
from src.app.embeddings.voyage import VOYAGE_DIMENSION, VOYAGE_MODEL, VoyageEmbedder
from src.app.exceptions.embeddings import EmbeddingConfigurationError


def test_bge_m3_reexports_the_canonical_revision() -> None:
    assert bge_m3.BGE_M3_REVISION == BGE_M3_REVISION


def test_bge_m3_wraps_sentence_transformer(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    class FakeSentenceTransformer:
        def __init__(self, model_name: str, *, device: str, revision: str) -> None:
            captured["model_name"] = model_name
            captured["device"] = device
            captured["revision"] = revision

        def encode(self, texts: list[str], *, normalize_embeddings: bool) -> list[list[float]]:
            captured["texts"] = texts
            captured["normalize"] = normalize_embeddings
            return [[1, 0] for _ in texts]

    module = ModuleType("sentence_transformers")
    module.SentenceTransformer = FakeSentenceTransformer  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sentence_transformers", module)

    revision = "0123456789abcdef0123456789abcdef01234567"
    embedder = BgeM3Embedder(device="cuda", revision=revision)

    assert embedder.model_name == BGE_M3_MODEL
    assert embedder.revision == revision
    assert embedder.dimension == 1024
    assert embedder.embed(["a", "b"]) == [[1.0, 0.0], [1.0, 0.0]]
    assert captured == {
        "model_name": BGE_M3_MODEL,
        "device": "cuda",
        "revision": revision,
        "texts": ["a", "b"],
        "normalize": True,
    }


def test_bge_m3_missing_extra_is_a_configuration_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "sentence_transformers", None)

    with pytest.raises(EmbeddingConfigurationError):
        BgeM3Embedder()


def test_bge_m3_default_revision_is_pinned() -> None:
    module = ModuleType("sentence_transformers")

    class FakeSentenceTransformer:
        def __init__(self, _model_name: str, *, device: str, revision: str) -> None:
            del device
            assert revision == BGE_M3_REVISION

    module.SentenceTransformer = FakeSentenceTransformer  # type: ignore[attr-defined]
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setitem(sys.modules, "sentence_transformers", module)

        embedder = BgeM3Embedder()

    assert embedder.revision == BGE_M3_REVISION


def test_voyage_wraps_api_client(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    class Result:
        embeddings: ClassVar[list[list[float]]] = [[0.5, 0.25]]
        total_tokens = 7

    class FakeClient:
        def __init__(self, *, api_key: str, max_retries: int) -> None:
            captured["api_key"] = api_key
            captured["max_retries"] = max_retries

        def embed(
            self,
            texts: list[str],
            *,
            model: str,
            input_type: str | None,
            output_dimension: int,
        ) -> Result:
            captured.update(
                texts=texts,
                model=model,
                input_type=input_type,
                output_dimension=output_dimension,
            )
            return Result()

    module = ModuleType("voyageai.client")
    module.Client = FakeClient  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "voyageai.client", module)

    embedder = VoyageEmbedder(api_key=SecretStr("secret"), max_retries=0)

    assert embedder.model_name == VOYAGE_MODEL
    assert embedder.dimension == VOYAGE_DIMENSION
    assert embedder.embed(["intent"]) == [[0.5, 0.25]]
    assert embedder.total_tokens == 7
    assert embedder.embed([]) == []
    assert embedder.total_tokens == 7
    assert captured == {
        "api_key": "secret",
        "max_retries": 0,
        "texts": ["intent"],
        "model": VOYAGE_MODEL,
        "input_type": None,
        "output_dimension": 1024,
    }


def test_voyage_missing_extra_is_a_configuration_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "voyageai.client", None)

    with pytest.raises(EmbeddingConfigurationError):
        VoyageEmbedder(api_key=SecretStr("secret"))
