"""Compare embedding models on the same labeled widget-search corpus."""

import argparse
import asyncio
import hashlib
import json
import math
import os
import platform
import sys
import time
from collections.abc import Iterator, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import UUID

import anyio.to_thread
from pgvector.sqlalchemy import Vector
from pydantic import BaseModel, Field
from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from src.app.contracts.solver.widget_candidate import WidgetMatch
from src.app.core.settings.embeddings import get_embeddings_settings
from src.app.db.session import build_engine
from src.app.embeddings.base import Embedder
from src.app.embeddings.factory import create_embedder
from src.app.embeddings.voyage import VoyageEmbedder
from src.app.models.widget_description import EMBEDDING_DIM
from src.app.repositories.widget_search_repository import WidgetSearchRepository

DATA = Path(__file__).with_name("data")
BATCH_SIZE = 32
OVERFETCH = 40
TOP_K = 5
VOYAGE_USD_PER_MILLION = 0.06
VOYAGE_WIN_MARGIN = 0.05

Language = Literal["en", "ru"]
Split = Literal["calibration", "test"]


class Widget(BaseModel):
    widget_id: UUID
    language: Language
    descriptions: list[str] = Field(min_length=1)


class Intent(BaseModel):
    intent: str = Field(min_length=1)
    widget_id: UUID | None
    language: Language
    split: Split


@dataclass(frozen=True)
class Corpus:
    widgets: list[Widget]
    intents: list[Intent]
    fingerprint: str

    @property
    def texts(self) -> list[str]:
        return [
            *(description for widget in self.widgets for description in widget.descriptions),
            *(intent.intent for intent in self.intents),
        ]


@dataclass(frozen=True)
class ScoredIntent:
    intent: Intent
    matches: list[WidgetMatch]
    cross_language: bool = False

    def expected_distance(self) -> float | None:
        return next((match.distance for match in self.matches if match.widget_id == self.intent.widget_id), None)


@dataclass(frozen=True)
class Scores:
    positives: int
    negatives: int
    recall_at_1: float | None
    recall_at_5: float | None
    mrr_at_5: float | None
    negative_acceptance: float | None


def _rows[T: BaseModel](contents: bytes, path: Path, model: type[T]) -> list[T]:
    rows: list[T] = []
    for number, line in enumerate(contents.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rows.append(model.model_validate_json(line))
        except ValueError as exc:
            raise ValueError(f"{path}:{number}: {exc}") from exc
    return rows


def load_corpus(library: Path, intents: Path) -> Corpus:
    library_bytes = library.read_bytes()
    intent_bytes = intents.read_bytes()
    widgets = _rows(library_bytes, library, Widget)
    queries = _rows(intent_bytes, intents, Intent)
    ids = {widget.widget_id for widget in widgets}
    if not widgets or len(widgets) != len(ids):
        raise ValueError("The library must contain unique widget IDs.")
    splits_by_widget: dict[UUID, Split] = {}
    for query in queries:
        if query.widget_id is None:
            continue
        if query.widget_id not in ids:
            raise ValueError(f"Unknown expected widget ID: {query.widget_id}")
        if splits_by_widget.setdefault(query.widget_id, query.split) != query.split:
            raise ValueError(f"Widget {query.widget_id} appears in both calibration and test intents.")
    for split in ("calibration", "test"):
        labels = {query.widget_id is None for query in queries if query.split == split}
        if labels != {False, True}:
            raise ValueError(f"{split} must contain positive and no-match intents.")
    fingerprint = hashlib.sha256(library_bytes + b"\x00" + intent_bytes).hexdigest()
    corpus = Corpus(widgets, queries, fingerprint)
    if any(not value or value != " ".join(value.split()) for value in corpus.texts):
        raise ValueError("Descriptions and intents must be nonempty and normalized with single spaces.")
    if len({value.casefold() for value in corpus.texts}) != len(corpus.texts):
        raise ValueError("Descriptions and intents must be distinct.")
    return corpus


def _batches(texts: list[str]) -> Iterator[list[str]]:
    for start in range(0, len(texts), BATCH_SIZE):
        yield texts[start : start + BATCH_SIZE]


def _percentile(values: Sequence[float], quantile: float) -> float:
    return sorted(values)[math.ceil(quantile * len(values)) - 1]


def _score(rows: Sequence[ScoredIntent], threshold: float = math.inf) -> Scores:
    ranks: list[int | None] = []
    negative_total = negative_accepted = 0
    for row in rows:
        if row.intent.widget_id is None:
            negative_total += 1
            negative_accepted += any(match.distance <= threshold for match in row.matches)
            continue
        ranks.append(
            next(
                (
                    rank
                    for rank, match in enumerate(row.matches, start=1)
                    if match.widget_id == row.intent.widget_id and match.distance <= threshold
                ),
                None,
            )
        )
    return Scores(
        positives=len(ranks),
        negatives=negative_total,
        recall_at_1=sum(rank == 1 for rank in ranks) / len(ranks) if ranks else None,
        recall_at_5=sum(rank is not None for rank in ranks) / len(ranks) if ranks else None,
        mrr_at_5=sum(1 / rank for rank in ranks if rank is not None) / len(ranks) if ranks else None,
        negative_acceptance=negative_accepted / negative_total if negative_total else None,
    )


def _calibrate(rows: Sequence[ScoredIntent]) -> float | None:
    """Choose the strictest deployable cutoff that preserves all calibration top-five hits."""
    distances = [distance for row in rows if (distance := row.expected_distance()) is not None]
    if not distances:
        return None
    return min(2.0, math.ceil(max(distances) * 10_000) / 10_000)


async def _embed(embedder: Embedder, texts: list[str]) -> tuple[list[list[float]], list[float]]:
    vectors = []
    full_batch_times = []
    for batch in _batches(texts):
        started = time.perf_counter()
        result = await anyio.to_thread.run_sync(embedder.embed, batch)
        elapsed = time.perf_counter() - started
        if len(result) != len(batch) or any(
            len(vector) != EMBEDDING_DIM or not all(math.isfinite(value) for value in vector) or not any(vector)
            for vector in result
        ):
            raise ValueError(f"{embedder.model_name} returned malformed or zero vectors.")
        vectors.extend(result)
        if len(batch) == BATCH_SIZE:
            full_batch_times.append(elapsed)
    return vectors, full_batch_times


async def _create_tables(conn: AsyncConnection) -> None:
    vector_version = await conn.scalar(text("SELECT extversion FROM pg_extension WHERE extname = 'vector'"))
    if vector_version is None or tuple(int(part) for part in vector_version.split(".")[:2]) < (0, 8):
        raise ValueError("The benchmark database requires the vector extension at version 0.8 or newer.")
    await conn.execute(text("CREATE TEMP TABLE widgets (id uuid PRIMARY KEY, status text NOT NULL) ON COMMIT DROP"))
    await conn.execute(
        text(
            "CREATE TEMP TABLE widget_descriptions (id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, "
            "widget_id uuid NOT NULL, text text NOT NULL, "
            f"embedding vector({EMBEDDING_DIM}) NOT NULL) ON COMMIT DROP"
        )
    )


async def _retrieve(conn: AsyncConnection, corpus: Corpus, vectors: list[list[float]]) -> list[ScoredIntent]:
    widget_languages = {widget.widget_id: widget.language for widget in corpus.widgets}
    await conn.execute(
        text("INSERT INTO pg_temp.widgets (id, status) VALUES (:id, 'active')"),
        [{"id": widget_id} for widget_id in widget_languages],
    )
    vectors_iter = iter(vectors)
    await conn.execute(
        text(
            "INSERT INTO pg_temp.widget_descriptions (widget_id, text, embedding) "
            "VALUES (:widget_id, :description, :embedding)"
        ).bindparams(bindparam("embedding", type_=Vector(EMBEDDING_DIM))),
        [
            {"widget_id": widget.widget_id, "description": description, "embedding": next(vectors_iter)}
            for widget in corpus.widgets
            for description in widget.descriptions
        ],
    )
    await conn.execute(
        text(
            "CREATE INDEX ON pg_temp.widget_descriptions USING hnsw (embedding vector_cosine_ops) "
            "WITH (m = 16, ef_construction = 128)"
        )
    )
    await conn.execute(text("ANALYZE pg_temp.widget_descriptions"))
    async with AsyncSession(bind=conn) as session:
        search = WidgetSearchRepository(session)
        return [
            ScoredIntent(
                intent,
                await search.find_nearest_widgets(query_vector=vector, k=TOP_K, overfetch=OVERFETCH),
                intent.widget_id is not None and widget_languages[intent.widget_id] != intent.language,
            )
            for intent, vector in zip(corpus.intents, vectors_iter, strict=True)
        ]


async def _run(corpus: Corpus, db_url: str, allow_voyage: bool) -> dict[str, object]:
    settings = get_embeddings_settings()
    if settings.provider == "voyage" and not allow_voyage:
        raise ValueError("Voyage uses a paid API. Pass --allow-voyage to authorize the benchmark calls.")
    if settings.provider == "bge_m3" and settings.device != "cpu":
        raise ValueError("The BGE benchmark requires EMBEDDINGS_DEVICE=cpu.")
    engine = build_engine(db_url, null_pool=True)
    try:
        async with engine.begin() as conn:
            await _create_tables(conn)
            embedder = await anyio.to_thread.run_sync(lambda: create_embedder(settings, voyage_max_retries=0))
            try:
                vectors, batch_times = await _embed(embedder, corpus.texts)
                ranked = await _retrieve(conn, corpus, vectors)
            except Exception:
                if isinstance(embedder, VoyageEmbedder):
                    print(f"Voyage usage from completed responses: {embedder.total_tokens} tokens", file=sys.stderr)
                raise
    finally:
        await engine.dispose()

    calibration = [row for row in ranked if row.intent.split == "calibration"]
    test = [row for row in ranked if row.intent.split == "test"]
    cross_language = [row for row in test if row.cross_language]
    threshold = _calibrate(calibration)
    tokens = embedder.total_tokens if isinstance(embedder, VoyageEmbedder) else None
    return {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "host": {
            "os": platform.system(),
            "arch": platform.machine(),
            "logical_cpus": len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else os.cpu_count(),
        },
        "provider": settings.provider,
        "model": embedder.model_name,
        "corpus_sha256": corpus.fingerprint,
        "batch_size": BATCH_SIZE,
        "embedding_batches": math.ceil(len(corpus.texts) / BATCH_SIZE),
        "full_latency_batches": len(batch_times),
        "p95_batch_seconds": _percentile(batch_times, 0.95) if batch_times else None,
        "total_tokens": tokens,
        "usd_per_million_tokens": VOYAGE_USD_PER_MILLION if tokens is not None else None,
        "api_cost_usd": tokens * VOYAGE_USD_PER_MILLION / 1_000_000 if tokens is not None else 0.0,
        "calibrated_max_distance": threshold,
        "calibration_unfiltered": asdict(_score(calibration)),
        "calibration_calibrated": asdict(_score(calibration, threshold)) if threshold is not None else None,
        "test_unfiltered": asdict(_score(test)),
        "test_at_initial_0_55": asdict(_score(test, 0.55)),
        "test_calibrated": asdict(_score(test, threshold)) if threshold is not None else None,
        "test_cross_language_unfiltered": asdict(_score(cross_language)),
        "test_cross_language_calibrated": asdict(_score(cross_language, threshold)) if threshold is not None else None,
    }


class ComparisonRun(BaseModel):
    provider: str
    corpus_sha256: str
    test_unfiltered: dict[str, float]


def _compare(paths: Sequence[Path]) -> dict[str, object]:
    runs = [ComparisonRun.model_validate_json(path.read_bytes()) for path in paths]
    by_provider = {run.provider: run for run in runs}
    if by_provider.keys() != {"bge_m3", "voyage"}:
        raise ValueError("Comparison requires one BGE-M3 run and one Voyage run.")
    bge = by_provider["bge_m3"]
    voyage = by_provider["voyage"]
    if bge.corpus_sha256 != voyage.corpus_sha256:
        raise ValueError("Both runs must use the same corpus.")
    delta = voyage.test_unfiltered["recall_at_5"] - bge.test_unfiltered["recall_at_5"]
    selected = "voyage" if delta >= VOYAGE_WIN_MARGIN or math.isclose(delta, VOYAGE_WIN_MARGIN) else "bge_m3"
    return {"voyage_minus_bge_recall_at_5_pp": round(100 * delta, 6), "recommended_provider": selected}


def _plan(corpus: Corpus) -> dict[str, object]:
    texts = corpus.texts
    utf8_bytes = sum(len(value.encode("utf-8")) for value in texts)
    languages = {widget.widget_id: widget.language for widget in corpus.widgets}
    return {
        "widgets": len(corpus.widgets),
        "descriptions": len(texts) - len(corpus.intents),
        "labeled_intents": sum(intent.widget_id is not None for intent in corpus.intents),
        "cross_language_intents": sum(
            intent.widget_id is not None and intent.language != languages[intent.widget_id] for intent in corpus.intents
        ),
        "no_match_intents": sum(intent.widget_id is None for intent in corpus.intents),
        "corpus_sha256": corpus.fingerprint,
        "embedding_inputs": len(texts),
        "embedding_batches": math.ceil(len(texts) / BATCH_SIZE),
        "full_latency_batches": len(texts) // BATCH_SIZE,
        "input_utf8_bytes": utf8_bytes,
        "voyage_usd_estimate_at_one_token_per_input_byte_plus_two_per_text": (
            (utf8_bytes + 2 * len(texts)) * VOYAGE_USD_PER_MILLION / 1_000_000
        ),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library", type=Path, default=DATA / "search_library.jsonl")
    parser.add_argument("--intents", type=Path, default=DATA / "search_intents.jsonl")
    parser.add_argument("--db-url", default=os.environ.get("DB_URL"), help="Async pgvector DSN (or set DB_URL).")
    parser.add_argument("--allow-voyage", action="store_true", help="Allow Voyage API calls for this run.")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--plan", action="store_true", help="Validate inputs and show the call count without embedding.")
    modes.add_argument("--compare", type=Path, nargs=2, metavar=("BGE_JSON", "VOYAGE_JSON"))
    args = parser.parse_args(argv)
    try:
        if args.compare:
            result = _compare(args.compare)
        else:
            corpus = load_corpus(args.library, args.intents)
            if args.plan:
                result = _plan(corpus)
            elif args.db_url:
                result = asyncio.run(_run(corpus, args.db_url, args.allow_voyage))
            else:
                parser.error("--db-url or DB_URL is required")
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
