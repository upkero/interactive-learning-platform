"""Integration tests of the widget vector search (story 2.3).

Postgres + pgvector only; skipped automatically when no database is
reachable. The SQL is exercised through the repository, never through a
fake, so ``DISTINCT ON``, the status filter and the primitive filter are
checked against the real planner.
"""

import math
import os
import random
import re
import warnings
from collections.abc import Sequence
from time import perf_counter
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event, insert, text
from sqlalchemy.exc import SADeprecationWarning
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from src.app.bootstrap.container import ApplicationContainer
from src.app.contracts.widgets import WidgetKind
from src.app.core.settings.solver import SolverSettings
from src.app.interfaces.embeddings.embedding_service import EmbeddingServiceInterface
from src.app.models.widget import Widget
from src.app.models.widget_description import EMBEDDING_DIM, WidgetDescription
from src.app.repositories.primitive_repository import PrimitiveRepository
from src.app.repositories.widget_description_repository import WidgetDescriptionRepository
from src.app.repositories.widget_repository import WidgetRepository
from src.app.repositories.widget_search_repository import WidgetSearchRepository
from src.app.services.solver.search.widget_search import WidgetSearch
from tests.support.fakes.observability.metrics_collector import RecordingMetricsCollector
from tests.support.types import SessionFactory
from tests.support.widget_search_latency import (
    LATENCY_LIMIT_MS,
    assert_p95_below,
    nearest_rank_percentile,
)

pytestmark = pytest.mark.integration

PRODUCTION_SEARCH_MAX_DISTANCE = cast(float, SolverSettings.model_fields["search_max_distance"].default)


class _FakeEmbeddingService(EmbeddingServiceInterface):
    def __init__(self, vector: list[float]) -> None:
        self._vector = vector
        self.calls: list[list[str]] = []

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return [self._vector for _ in texts]


def _unit(primary: float = 1.0, secondary: float = 0.0, *, third: float = 0.0) -> list[float]:
    vector = [0.0] * EMBEDDING_DIM
    vector[0] = primary
    vector[1] = secondary
    vector[2] = third
    norm = math.sqrt(primary * primary + secondary * secondary + third * third)
    return [value / norm for value in vector]


async def _primitive(session_factory: SessionFactory, primitive_id: str) -> None:
    async with session_factory() as session, session.begin():
        await PrimitiveRepository(session).upsert(
            primitive_id=primitive_id,
            version="1.0.0",
            description=primitive_id,
            modes=["explore"],
            params_schema={},
        )


async def _config_widget(
    session_factory: SessionFactory,
    *,
    primitive_id: str,
    descriptions: list[tuple[str, list[float]]],
) -> UUID:
    async with session_factory() as session, session.begin():
        widget = await WidgetRepository(session).create(
            kind=WidgetKind.CONFIG,
            primitive_id=primitive_id,
            mode="explore",
            params={},
        )
        repository = WidgetDescriptionRepository(session)
        for index, (description, vector) in enumerate(descriptions):
            await repository.create(
                widget_id=widget.id,
                text=description,
                is_paraphrase=index > 0,
                embedding=vector,
            )
    return widget.id


async def test_widget_with_several_close_descriptions_is_returned_once(session_factory: SessionFactory) -> None:
    await _primitive(session_factory, "three-frame")
    first = await _config_widget(
        session_factory,
        primitive_id="three-frame",
        descriptions=[
            ("main", _unit()),
            ("paraphrase one", _unit(0.99, 0.1)),
            ("paraphrase two", _unit(0.98, 0.2)),
        ],
    )
    second = await _config_widget(
        session_factory,
        primitive_id="three-frame",
        descriptions=[("orthogonal", _unit(0.0, 1.0))],
    )

    async with session_factory() as session:
        matches = await WidgetSearchRepository(session).find_nearest_widgets(
            query_vector=_unit(),
            k=5,
            overfetch=40,
        )

    ids = [match.widget_id for match in matches]
    assert ids == [first, second]
    assert ids.count(first) == 1
    assert matches[0].matched_text == "main"
    assert [match.distance for match in matches] == sorted(match.distance for match in matches)


async def test_top_k_returns_distinct_widgets_within_description_count_invariant(
    session_factory: SessionFactory,
) -> None:
    """Top-k stays distinct for the documented 4-6 descriptions per widget."""
    await _primitive(session_factory, "three-frame")
    widget_ids: list[UUID] = []

    for widget_index in range(7):
        descriptions: list[tuple[str, list[float]]] = []
        for description_index in range(6):
            target_distance = widget_index * 0.006 + description_index * 0.001
            vector = _unit(
                1.0 - target_distance,
                math.sqrt(target_distance * (2.0 - target_distance)),
            )
            descriptions.append((f"widget {widget_index} description {description_index}", vector))
        widget_ids.append(
            await _config_widget(
                session_factory,
                primitive_id="three-frame",
                descriptions=descriptions,
            )
        )

    async with session_factory() as session:
        matches = await WidgetSearchRepository(session).find_nearest_widgets(
            query_vector=_unit(),
            k=5,
            overfetch=40,
        )

    ids = [match.widget_id for match in matches]
    distances = [match.distance for match in matches]
    assert len(matches) == 5
    assert len(set(ids)) == 5
    assert ids == widget_ids[:5]
    assert all(distances[index] <= distances[index + 1] + 1e-9 for index in range(len(distances) - 1))
    assert ids.count(widget_ids[0]) == 1


@pytest.mark.parametrize("status", ["excluded", "merged"])
async def test_inactive_widget_is_never_returned(db: AsyncEngine, session_factory: SessionFactory, status: str) -> None:
    await _primitive(session_factory, "three-frame")
    visible = await _config_widget(
        session_factory,
        primitive_id="three-frame",
        descriptions=[("visible", _unit(0.8, 0.6))],
    )
    inactive = await _config_widget(
        session_factory,
        primitive_id="three-frame",
        descriptions=[("inactive", _unit())],
    )

    async with db.connect() as connection:
        if status == "merged":
            # Story 2.8 writes merged. Simulate that schema in this transaction.
            await connection.execute(text("ALTER TABLE widgets DROP CONSTRAINT IF EXISTS ck_widgets_status"))
        await connection.execute(
            text("UPDATE widgets SET status = :status, canonical_id = :canonical_id WHERE id = :id"),
            {"status": status, "canonical_id": visible if status == "merged" else None, "id": inactive},
        )
        search = WidgetSearch(
            session_factory=async_sessionmaker(connection),
            embeddings=_FakeEmbeddingService(_unit()),
            settings=SolverSettings(
                _env_file=None,
                search_overfetch=40,
                search_max_distance=PRODUCTION_SEARCH_MAX_DISTANCE,
            ),
            metrics=RecordingMetricsCollector(),
            search_repo=WidgetSearchRepository,
            widget_repo=WidgetRepository,
            primitive_repo=PrimitiveRepository,
        )
        candidates = await search.search("intent", k=1)
        await connection.rollback()

    assert [candidate.widget_id for candidate in candidates] == [visible]


async def test_primitive_filter_and_unfiltered_query(session_factory: SessionFactory) -> None:
    await _primitive(session_factory, "three-frame")
    await _primitive(session_factory, "key-terms")
    filtered = await _config_widget(
        session_factory,
        primitive_id="three-frame",
        descriptions=[("filtered", _unit(0.9, 0.1))],
    )
    other = await _config_widget(
        session_factory,
        primitive_id="key-terms",
        descriptions=[("other", _unit(0.0, 1.0))],
    )

    async with session_factory() as session:
        repository = WidgetSearchRepository(session)
        with_filter = await repository.find_nearest_widgets(
            query_vector=_unit(),
            k=5,
            overfetch=40,
            primitive_id="three-frame",
        )
        without_filter = await repository.find_nearest_widgets(
            query_vector=_unit(),
            k=5,
            overfetch=40,
        )

    assert [match.widget_id for match in with_filter] == [filtered]
    assert [match.widget_id for match in without_filter] == [filtered, other]


async def test_hnsw_candidate_list_covers_the_configured_overfetch(session_factory: SessionFactory) -> None:
    async with session_factory() as session:
        matches = await WidgetSearchRepository(session).find_nearest_widgets(
            query_vector=_unit(),
            k=1,
            overfetch=150,
        )
        ef_search = await session.scalar(text("SHOW hnsw.ef_search"))

    assert matches == []
    assert ef_search == "150"


async def test_distinct_on_implementations_do_not_use_the_deprecated_sqlalchemy_api(
    session_factory: SessionFactory,
) -> None:
    await _primitive(session_factory, "three-frame")
    widget = await _config_widget(
        session_factory,
        primitive_id="three-frame",
        descriptions=[("main", _unit())],
    )

    async with session_factory() as session:
        with warnings.catch_warnings():
            warnings.simplefilter("error", SADeprecationWarning)
            matches = await WidgetSearchRepository(session).find_nearest_widgets(
                query_vector=_unit(),
                k=1,
                overfetch=40,
            )
            enriched = await WidgetRepository(session).get_many_with_main_description([widget])

    assert [match.widget_id for match in matches] == [widget]
    assert enriched[widget].description == "main"


async def test_search_fills_short_primitive_result_after_threshold(
    db: AsyncEngine,
    session_factory: SessionFactory,
    container: ApplicationContainer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _primitive(session_factory, "three-frame")
    await _primitive(session_factory, "key-terms")
    filtered = await _config_widget(
        session_factory,
        primitive_id="three-frame",
        descriptions=[("main", _unit(0.6, 0.8)), ("closer paraphrase", _unit(0.8, 0.6))],
    )
    await _config_widget(
        session_factory,
        primitive_id="three-frame",
        descriptions=[("filtered but too far", _unit(0, 1))],
    )
    other = await _config_widget(
        session_factory,
        primitive_id="key-terms",
        descriptions=[("other", _unit())],
    )
    selects: list[str] = []

    def record_select(
        _conn: Any, _cursor: Any, statement: str, _parameters: Any, _context: Any, _executemany: bool
    ) -> None:
        if statement.startswith("SELECT"):
            selects.append(statement)

    embeddings = _FakeEmbeddingService(_unit())
    monkeypatch.setitem(container.__dict__, "embedding_service", embeddings)
    monkeypatch.setitem(container.__dict__, "session_factory", session_factory)
    monkeypatch.setitem(
        container.__dict__,
        "solver_settings",
        SolverSettings(
            _env_file=None,
            search_overfetch=40,
            search_max_distance=PRODUCTION_SEARCH_MAX_DISTANCE,
        ),
    )

    event.listen(db.sync_engine, "before_cursor_execute", record_select)
    try:
        candidates = await container.widget_search.search("intent", k=2, primitive_hint="three-frame")
    finally:
        event.remove(db.sync_engine, "before_cursor_execute", record_select)

    assert embeddings.calls == [["intent"]]
    assert [candidate.widget_id for candidate in candidates] == [filtered, other]
    assert candidates[0].matched_text == "closer paraphrase"
    assert candidates[0].description == "main"
    assert candidates[1].description == "other"
    assert len(selects) == 4  # Catalog, filtered search, fallback, bulk enrichment.


async def test_explain_of_search_uses_hnsw_index(db: AsyncEngine, session_factory: SessionFactory) -> None:
    """EXPLAIN the emitted search SQL on 200 widgets with five descriptions each."""
    await _primitive(session_factory, "three-frame")
    await _primitive(session_factory, "key-terms")
    rng = random.Random(7)
    widgets: list[dict[str, Any]] = []
    descriptions: list[dict[str, Any]] = []
    for index in range(200):
        widget_id = uuid4()
        widgets.append(
            {
                "id": widget_id,
                "kind": "config",
                "primitive_id": "three-frame" if index % 2 == 0 else "key-terms",
                "mode": "explore",
                "params": {},
                "status": "excluded" if index % 10 == 0 else "active",
            }
        )
        for number in range(5):
            vector = [rng.gauss(0, 0.025) for _ in range(EMBEDDING_DIM)]
            vector[index % 4] += 1
            descriptions.append(
                {
                    "widget_id": widget_id,
                    "text": f"Widget {index} description {number}",
                    "is_paraphrase": number > 0,
                    "embedding": vector,
                }
            )

    async with db.begin() as connection:
        await connection.execute(insert(Widget), widgets)
        await connection.execute(insert(WidgetDescription), descriptions)
        await connection.execute(text("ANALYZE widgets"))
        await connection.execute(text("ANALYZE widget_descriptions"))

    captured: list[tuple[str, tuple[Any, ...]]] = []

    def capture(
        _conn: Any, _cursor: Any, statement: str, parameters: tuple[Any, ...], _context: Any, _executemany: bool
    ) -> None:
        if statement.startswith("SELECT") and "<=>" in statement:
            captured.append((statement, parameters))

    async with session_factory() as session:
        connection = await session.connection()
        event.listen(connection.sync_connection, "before_cursor_execute", capture)
        try:
            for hint in (None, "three-frame"):
                matches = await WidgetSearchRepository(session).find_nearest_widgets(
                    query_vector=_unit(),
                    k=5,
                    overfetch=40,
                    primitive_id=hint,
                )
                assert len(matches) == 5
                assert [match.distance for match in matches] == sorted(match.distance for match in matches)
        finally:
            event.remove(connection.sync_connection, "before_cursor_execute", capture)

        assert len(captured) == 2
        for statement, parameters in captured:
            rows = await connection.exec_driver_sql(f"EXPLAIN (ANALYZE, BUFFERS) {statement}", parameters)
            plan = "\n".join(re.sub(r"\[[^]]+\]'::vector", "[...]'::vector", line) for line in rows.scalars())
            print(plan)
            assert "Index Scan using ix_widget_descriptions_embedding_hnsw" in plan

    if os.environ.get("ILP_MEASURE_WIDGET_SEARCH_LATENCY") != "1":
        return

    # Use normal pooled requests with no model or Redis time. The third case
    # exercises fallback because the key-terms vectors are outside the threshold.
    engine = create_async_engine(db.url, pool_pre_ping=True)
    search = WidgetSearch(
        session_factory=async_sessionmaker(engine),
        embeddings=_FakeEmbeddingService(_unit()),
        settings=SolverSettings(
            _env_file=None,
            search_overfetch=40,
            search_max_distance=PRODUCTION_SEARCH_MAX_DISTANCE,
        ),
        metrics=RecordingMetricsCollector(),
        search_repo=WidgetSearchRepository,
        widget_repo=WidgetRepository,
        primitive_repo=PrimitiveRepository,
    )
    try:
        measurements: list[tuple[str | None, list[float], float]] = []
        for hint in (None, "three-frame", "key-terms"):
            for _ in range(5):
                await search.search("intent", primitive_hint=hint)
            samples: list[float] = []
            for _ in range(100):
                started = perf_counter()
                candidates = await search.search("intent", primitive_hint=hint)
                samples.append((perf_counter() - started) * 1000)
                assert len(candidates) == 5
            p95 = nearest_rank_percentile(samples, 95)
            measurements.append((hint, samples, p95))
            print(
                f"WIDGET_SEARCH_LATENCY hint={hint or 'none'} p95_ms={p95:.3f} "
                f"limit_ms={LATENCY_LIMIT_MS:.3f} status={'pass' if p95 < LATENCY_LIMIT_MS else 'fail'}"
            )
        for _, samples, _ in measurements:
            assert_p95_below(samples, limit_ms=LATENCY_LIMIT_MS)
    finally:
        await engine.dispose()
