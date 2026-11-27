"""Local BGE-M3 embedder (story 2.3).

The import of ``sentence_transformers`` happens in ``__init__`` so the API
process starts without torch when the resolver is not used yet, and the
model is loaded once per worker by the factory cache. Vectors are
normalised, so cosine distance and dot product agree.
"""

from collections.abc import Sequence

from src.app.exceptions.embeddings import EmbeddingConfigurationError

BGE_M3_MODEL = "BAAI/bge-m3"


class BgeM3Embedder:
    """SentenceTransformers wrapper around ``BAAI/bge-m3``."""

    def __init__(self, *, device: str = "cpu", model_name: str = BGE_M3_MODEL) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - depends on the install extra
            raise EmbeddingConfigurationError(
                "sentence-transformers is not installed; install the embeddings-local extra."
            ) from exc
        self._model_name = model_name
        self._model = SentenceTransformer(model_name, device=device)

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return 1024

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = self._model.encode(list(texts), normalize_embeddings=True)
        return [[float(value) for value in vector] for vector in vectors]


__all__ = ["BGE_M3_MODEL", "BgeM3Embedder"]
