from random import Random

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from evals import embeddings_benchmark as benchmark
from src.app.core.settings.embeddings import get_embeddings_settings


@pytest.mark.integration
async def test_benchmark_runs_the_full_corpus_on_pgvector_with_fake_embeddings(
    db_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    corpus = benchmark.load_corpus(benchmark.DATA / "search_library.jsonl", benchmark.DATA / "search_intents.jsonl")
    index = {widget.widget_id: ordinal for ordinal, widget in enumerate(corpus.widgets)}
    positions = {value: index[widget.widget_id] for widget in corpus.widgets for value in widget.descriptions}
    positions.update({intent.intent: index[intent.widget_id] if intent.widget_id else 100 for intent in corpus.intents})
    batch_sizes: list[int] = []
    rng = Random(41)
    vectors = {position: [rng.uniform(-1, 1) for _ in range(1024)] for position in sorted(set(positions.values()))}

    class FakeEmbedder:
        model_name = "fake"
        dimension = 1024

        def embed(self, texts: list[str]) -> list[list[float]]:
            batch_sizes.append(len(texts))
            return [vectors[positions[value]] for value in texts]

    monkeypatch.setenv("EMBEDDINGS_PROVIDER", "bge_m3")
    monkeypatch.setenv("EMBEDDINGS_DEVICE", "cpu")
    get_embeddings_settings.cache_clear()
    monkeypatch.setattr(benchmark, "create_embedder", lambda *_args, **_kwargs: FakeEmbedder())
    db_url = db_engine.url.render_as_string(hide_password=False)
    async with db_engine.connect() as conn:
        before = await conn.scalar(text("SELECT count(*) FROM public.widgets"))
    try:
        result = await benchmark._run(corpus, db_url, allow_voyage=False)
    finally:
        get_embeddings_settings.cache_clear()
    async with db_engine.connect() as conn:
        assert await conn.scalar(text("SELECT count(*) FROM public.widgets")) == before

    assert batch_sizes == [32] * 13 + [4]
    assert result["calibrated_max_distance"] == 0.0
    assert result["test_calibrated"] == {
        "positives": 75,
        "negatives": 15,
        "recall_at_1": 1.0,
        "recall_at_5": 1.0,
        "mrr_at_5": 1.0,
        "negative_acceptance": 0.0,
    }
