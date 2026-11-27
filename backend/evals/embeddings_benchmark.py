"""Benchmark of embedding models on the widget-search corpus (story 2.3.1).

The corpus is JSONL with one row per intent::

    {"intent": "show how a weight changes the output", "widget_id": "..."}

Run it against a database that already contains the widgets::

    python -m evals.embeddings_benchmark evals/data/search_example.jsonl

The script prints recall@1, recall@5, MRR@5, the p95 time of one embedding
batch and the provider/model. The numbers go into ADR-0004; the threshold
SOLVER_SEARCH_MAX_DISTANCE is calibrated from the same run (2.3.1).
"""

import argparse
import asyncio
import json
import math
import statistics
import sys
import time
from collections.abc import Sequence
from pathlib import Path
from uuid import UUID

import anyio.to_thread
import redis.asyncio as aioredis

from src.app.core.settings.app import get_app_settings
from src.app.core.settings.embeddings import get_embeddings_settings
from src.app.core.settings.solver import SolverSettings
from src.app.db.session import build_engine, build_session_factory
from src.app.embeddings.factory import get_embedder
from src.app.observability.noop_metrics_collector import NoopMetricsCollector
from src.app.repositories.primitive_repository import PrimitiveRepository
from src.app.repositories.widget_repository import WidgetRepository
from src.app.repositories.widget_search_repository import WidgetSearchRepository
from src.app.services.solver.library.primitive_catalog import PrimitiveCatalog
from src.app.services.solver.search.embedding_service import EmbeddingService
from src.app.services.solver.search.instrumented_embedding_service import InstrumentedEmbeddingService
from src.app.services.solver.search.widget_search import WidgetSearch


def _load_corpus(path: Path) -> list[tuple[str, UUID]]:
    rows: list[tuple[str, UUID]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        rows.append((str(payload["intent"]), UUID(payload["widget_id"])))
    return rows


async def _run(path: Path) -> int:
    corpus = _load_corpus(path)
    settings = get_embeddings_settings()
    app_settings = get_app_settings()
    embedder = get_embedder(settings)
    redis = aioredis.Redis.from_url(settings.cache_redis_url)
    embeddings = InstrumentedEmbeddingService(
        service=EmbeddingService(
            embedder=embedder,
            redis=redis,
            metrics=NoopMetricsCollector(),
            batch_size=settings.batch_size,
            ttl_seconds=settings.cache_ttl_seconds,
        ),
        metrics=NoopMetricsCollector(),
    )
    engine = build_engine(str(app_settings.db_url), null_pool=True)
    try:
        session_factory = build_session_factory(engine)
        async with session_factory() as session:
            primitives = await PrimitiveRepository(session).list_all()
        search = WidgetSearch(
            session_factory=session_factory,
            embeddings=embeddings,
            catalog=PrimitiveCatalog.from_records(primitives),
            settings=SolverSettings(),
            metrics=NoopMetricsCollector(),
            search_repo=WidgetSearchRepository,
            widget_repo=WidgetRepository,
        )
        hits_at_1 = hits_at_5 = 0
        reciprocal_ranks: list[float] = []
        for intent, expected in corpus:
            results = await search.search(intent, k=5)
            ids = [candidate.widget_id for candidate in results]
            if expected in ids:
                rank = ids.index(expected) + 1
                hits_at_5 += 1
                hits_at_1 += int(rank == 1)
                reciprocal_ranks.append(1.0 / rank)
            else:
                reciprocal_ranks.append(0.0)

        # p95 of one model batch, cold cache not required for the shape of
        # the distribution; the cache hit rate is reported by metrics.
        batch_times: list[float] = []
        texts = list(dict.fromkeys(intent for intent, _ in corpus))
        for start in range(0, len(texts), settings.batch_size):
            batch = texts[start : start + settings.batch_size]
            started = time.perf_counter()
            await anyio.to_thread.run_sync(embedder.embed, batch)
            batch_times.append(time.perf_counter() - started)
        p95 = _percentile(batch_times, 0.95) if batch_times else math.nan
        total = len(corpus) or 1
        print("| model | provider | recall@1 | recall@5 | MRR@5 | p95 batch, s |")
        print("|---|---|---|---|---|---|")
        print(
            f"| {embedder.model_name} | {settings.provider} | {hits_at_1 / total:.3f} | "
            f"{hits_at_5 / total:.3f} | {statistics.fmean(reciprocal_ranks):.3f} | {p95:.3f} |"
        )
    finally:
        await redis.aclose()
        await engine.dispose()
    return 0


def _percentile(values: Sequence[float], quantile: float) -> float:
    ordered = sorted(values)
    index = max(0, math.ceil(quantile * len(ordered)) - 1)
    return ordered[index]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Benchmark embedding models on the widget search corpus.")
    parser.add_argument("corpus", type=Path, help="JSONL with intent/widget_id rows.")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    return asyncio.run(_run(args.corpus))


if __name__ == "__main__":
    raise SystemExit(main())
