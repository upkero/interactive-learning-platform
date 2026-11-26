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
from collections.abc import Sequence
from time import perf_counter
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event, insert, text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from src.app.bootstrap.container import ApplicationContainer
from src.app.contracts.widgets import WidgetKind
from src.app.core.settings.solver import SolverSettings
from src.app.models.widget import Widget
from src.app.models.widget_description import EMBEDDING_DIM, WidgetDescription
from src.app.repositories.primitive_repository import PrimitiveRepository
from src.app.repositories.widget_description_repository import WidgetDescriptionRepository
from src.app.repositories.widget_repository import WidgetRepository
from src.app.repositories.widget_search_repository import WidgetSearchRepository
from src.app.services.solver.search.widget_search import WidgetSearch
from tests.support.fakes.observability.metrics_collector import RecordingMetricsCollector
from tests.support.types import SessionFactory

pytestmark = pytest.mark.integration


class _FakeEmbeddingService:
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
            settings=SolverSettings(_env_file=None, search_overfetch=40, search_max_distance=0.55),
            metrics=RecordingMetricsCollector(),
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
        SolverSettings(_env_file=None, search_overfetch=40, search_max_distance=0.55),
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
        settings=SolverSettings(_env_file=None, search_overfetch=40, search_max_distance=0.55),
        metrics=RecordingMetricsCollector(),
    )
    try:
        for hint in (None, "three-frame", "key-terms"):
            for _ in range(5):
                await search.search("intent", primitive_hint=hint)
            samples: list[float] = []
            for _ in range(100):
                started = perf_counter()
                candidates = await search.search("intent", primitive_hint=hint)
                samples.append((perf_counter() - started) * 1000)
                assert len(candidates) == 5
            p95 = sorted(samples)[math.ceil(len(samples) * 0.95) - 1]
            print(f"Local search p95 (100 requests, primitive_hint={hint!r}): {p95:.2f} ms")
    finally:
        await engine.dispose()
