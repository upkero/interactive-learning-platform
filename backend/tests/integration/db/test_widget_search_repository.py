"""Integration tests of the widget vector search (story 2.3).

Postgres + pgvector only; skipped automatically when no database is
reachable. The SQL is exercised through the repository, never through a
fake, so ``DISTINCT ON``, the status filter and the primitive filter are
checked against the real planner.
"""

import math
import random
from collections.abc import Sequence
from uuid import UUID

import pytest
from sqlalchemy import text

from src.app.contracts.widgets import WidgetKind, WidgetStatus
from src.app.core.settings.solver import SolverSettings
from src.app.models.widget_description import EMBEDDING_DIM
from src.app.repositories.primitive_repository import PrimitiveRepository
from src.app.repositories.widget_description_repository import WidgetDescriptionRepository
from src.app.repositories.widget_repository import WidgetRepository
from src.app.repositories.widget_search_repository import EF_SEARCH, WidgetSearchRepository, _nearest_widgets_statement
from src.app.services.solver.library.primitive_catalog import PrimitiveCatalog
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


async def test_excluded_widget_is_never_returned(session_factory: SessionFactory) -> None:
    await _primitive(session_factory, "three-frame")
    visible = await _config_widget(
        session_factory,
        primitive_id="three-frame",
        descriptions=[("visible", _unit(0.0, 1.0))],
    )
    excluded = await _config_widget(
        session_factory,
        primitive_id="three-frame",
        descriptions=[("excluded", _unit())],
    )
    async with session_factory() as session, session.begin():
        await WidgetRepository(session).set_status(excluded, WidgetStatus.EXCLUDED)

    async with session_factory() as session:
        matches = await WidgetSearchRepository(session).find_nearest_widgets(
            query_vector=_unit(),
            k=5,
            overfetch=40,
        )

    assert [match.widget_id for match in matches] == [visible]


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


async def test_service_fills_short_primitive_result_without_filter(session_factory: SessionFactory) -> None:
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
        descriptions=[("other", _unit(1.0, 1.0))],
    )
    await _config_widget(
        session_factory,
        primitive_id="key-terms",
        descriptions=[("out of range", _unit(0.0, 1.0))],
    )
    embeddings = _FakeEmbeddingService(_unit())
    search = WidgetSearch(
        session_factory=session_factory,
        embeddings=embeddings,
        catalog=PrimitiveCatalog(["three-frame"]),
        settings=SolverSettings(_env_file=None, search_overfetch=40, search_max_distance=0.55),
        metrics=RecordingMetricsCollector(),
        search_repo=WidgetSearchRepository,
        widget_repo=WidgetRepository,
    )

    candidates = await search.search("intent", k=3, primitive_hint="three-frame")

    assert embeddings.calls == [["intent"]]
    assert [candidate.widget_id for candidate in candidates] == [filtered, other]
    assert candidates[0].description == "filtered"
    assert candidates[1].description == "other"


async def test_explain_of_search_uses_hnsw_index(session_factory: SessionFactory) -> None:
    """Verify HNSW eligibility for the repository's nearest-neighbor ordering."""
    await _primitive(session_factory, "three-frame")
    rng = random.Random(7)
    vectors: list[list[float]] = []
    for _ in range(1000):
        vector = [rng.gauss(0.0, 1.0) for _ in range(EMBEDDING_DIM)]
        norm = math.sqrt(sum(value * value for value in vector))
        vectors.append([value / norm for value in vector])
    await _config_widget(
        session_factory,
        primitive_id="three-frame",
        descriptions=[(f"description {index}", vector) for index, vector in enumerate(vectors)],
    )
    statement = _nearest_widgets_statement(vectors[0], k=5, overfetch=40, primitive_id=None)
    async with session_factory() as session:
        query = statement.compile(dialect=session.get_bind().dialect, compile_kwargs={"literal_binds": True})
        await session.execute(text("ANALYZE widgets, widget_descriptions"))
        # For this small fixture, PostgreSQL can prefer a scan followed by an explicit sort.
        # Discourage that sort to verify the KNN ordering can use HNSW.
        await session.execute(text("SET LOCAL enable_sort = off"))
        await session.execute(text(f"SET LOCAL hnsw.ef_search = {EF_SEARCH}"))
        await session.execute(text("SET LOCAL hnsw.iterative_scan = relaxed_order"))
        plan_rows = (await session.execute(text(f"EXPLAIN {query}"))).scalars().all()
    plan = "\n".join(plan_rows)
    assert "Index Scan using ix_widget_descriptions_embedding_hnsw" in plan, plan
