"""Unit tests of the widget resolver (story 2.4)."""

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.contracts.solver.main_pass import DirectiveKind, MainPassDirective, PrimitiveMode
from src.app.contracts.solver.widget_candidate import WidgetCandidate, WidgetMatch
from src.app.contracts.widgets import WidgetKind, WidgetRecord, WidgetStatus
from src.app.core.settings.solver import SolverSettings
from src.app.services.solver.library.primitive_catalog import PrimitiveCatalog
from src.app.services.solver.resolve.widget_resolver import WidgetResolver
from src.app.services.solver.search.widget_search import WidgetSearch
from tests.support.fakes.db.session import FakeSession
from tests.support.fakes.observability.metrics_collector import RecordingMetricsCollector
from tests.support.fakes.repositories.widgets import FakeWidgetRepository

pytestmark = pytest.mark.unit


class FakeEmbeddingService:
    def __init__(self, vectors: list[list[float]] | None = None) -> None:
        self.vectors = vectors if vectors is not None else [[0.1, 0.2, 0.3, 0.4]]
        self.calls: list[list[str]] = []

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return self.vectors


class ScriptedSearchRepository:
    def __init__(self, responses: list[list[WidgetMatch]]) -> None:
        self.responses = responses
        self.calls: list[dict[str, object]] = []

    async def find_nearest_widgets(
        self,
        *,
        query_vector: Sequence[float],
        k: int,
        overfetch: int,
        primitive_id: str | None = None,
    ) -> list[WidgetMatch]:
        self.calls.append(
            {
                "query_vector": list(query_vector),
                "k": k,
                "overfetch": overfetch,
                "primitive_id": primitive_id,
            }
        )
        return self.responses.pop(0) if self.responses else []


def _settings(*, max_widgets_per_part: int = 6) -> SolverSettings:
    return SolverSettings(_env_file=None, max_widgets_per_part=max_widgets_per_part)


def _make_widget_record(widget_id: UUID) -> WidgetRecord:
    return WidgetRecord(
        id=widget_id,
        kind=WidgetKind.CONFIG,
        primitive_id="three-frame",
        mode="explore",
        params={},
        source_tsx=None,
        compiled_js=None,
        status=WidgetStatus.ACTIVE,
        canonical_id=None,
        version=1,
        created_from_part_id=None,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _candidate(widget_id: UUID, distance: float = 0.2) -> WidgetCandidate:
    return WidgetCandidate(
        widget_id=widget_id,
        kind=WidgetKind.CONFIG,
        primitive_id="three-frame",
        mode="explore",
        params={},
        matched_text="matched description",
        description="Main description",
        distance=distance,
    )


def _resolver(
    *,
    responses: list[list[WidgetMatch]],
    widgets: list[WidgetRecord] | None = None,
    catalog: PrimitiveCatalog | None = None,
    settings: SolverSettings | None = None,
    metrics: RecordingMetricsCollector | None = None,
) -> tuple[WidgetResolver, ScriptedSearchRepository, RecordingMetricsCollector]:
    repository = ScriptedSearchRepository(responses)
    collector = metrics or RecordingMetricsCollector()
    session_factory = cast(async_sessionmaker[AsyncSession], lambda: FakeSession())
    widget_repo = FakeWidgetRepository()
    for widget in widgets or []:
        widget_repo._widgets[widget.id] = widget
    search = WidgetSearch(
        session_factory=session_factory,
        embeddings=FakeEmbeddingService(),
        catalog=catalog or PrimitiveCatalog(),
        settings=settings or _settings(),
        metrics=collector,
        search_repo=lambda _session: repository,
        widget_repo=lambda _session: widget_repo,
    )
    resolver = WidgetResolver(
        search=search,
        catalog=catalog or PrimitiveCatalog(),
        settings=settings or _settings(),
        metrics=collector,
    )
    return resolver, repository, collector


def _directive(
    ref: str,
    *,
    kind: DirectiveKind = "widget",
    intent: str = "show a chart",
    primitive_hint: str | None = None,
    mode_hint: PrimitiveMode | None = None,
    image_id: str | None = None,
) -> MainPassDirective:
    return MainPassDirective(
        ref=ref,
        kind=kind,
        intent=intent,
        source_span="Quoted source text.",
        primitive_hint=primitive_hint,
        mode_hint=mode_hint,
        image_id=image_id,
    )


async def test_resolve_widget_directives_picks_closest_candidate() -> None:
    w1 = uuid4()
    w2 = uuid4()
    resolver, repository, _ = _resolver(
        responses=[
            [
                WidgetMatch(widget_id=w1, matched_text="closest", distance=0.1),
                WidgetMatch(widget_id=w2, matched_text="other", distance=0.3),
            ]
        ],
        widgets=[_make_widget_record(w1), _make_widget_record(w2)],
        catalog=PrimitiveCatalog(["three-frame"]),
    )

    directives = [_directive("w1", intent="show the weight", primitive_hint="three-frame")]
    resolutions = await resolver.resolve(directives=directives)

    assert len(resolutions) == 1
    assert resolutions[0].ref == "w1"
    assert resolutions[0].widget_id == w1
    assert resolutions[0].candidate.distance == 0.1
    assert repository.calls[0]["primitive_id"] == "three-frame"


async def test_unknown_primitive_hint_is_ignored() -> None:
    w1 = uuid4()
    resolver, repository, _ = _resolver(
        responses=[[WidgetMatch(widget_id=w1, matched_text="d", distance=0.1)]],
        widgets=[_make_widget_record(w1)],
        catalog=PrimitiveCatalog(["three-frame"]),
    )

    directives = [_directive("w1", intent="intent", primitive_hint="no-such-primitive")]
    await resolver.resolve(directives=directives)

    assert repository.calls[0]["primitive_id"] is None


async def test_no_candidate_leaves_directive_unresolved() -> None:
    resolver, _, metrics = _resolver(responses=[[]])

    directives = [_directive("w1", intent="intent")]
    resolutions = await resolver.resolve(directives=directives)

    assert resolutions == []
    assert ("widget_resolver.unresolved", {}, 1) in metrics.labeled_counters


async def test_non_widget_directives_are_skipped() -> None:
    w1 = uuid4()
    resolver, _, _ = _resolver(
        responses=[[WidgetMatch(widget_id=w1, matched_text="d", distance=0.1)]],
        widgets=[_make_widget_record(w1)],
    )

    directives = [
        _directive("img_1", kind="image", intent="show image", image_id="img_1"),
        _directive("q1", kind="quiz", intent="ask question"),
        _directive("w1", kind="widget", intent="show widget"),
    ]
    resolutions = await resolver.resolve(directives=directives)

    assert len(resolutions) == 1
    assert resolutions[0].ref == "w1"


async def test_empty_directives_returns_empty() -> None:
    resolver, _, _ = _resolver(responses=[])
    assert await resolver.resolve(directives=[]) == []


async def test_multiple_widget_directives_all_resolved() -> None:
    w1 = uuid4()
    w2 = uuid4()
    resolver, repository, _ = _resolver(
        responses=[
            [WidgetMatch(widget_id=w1, matched_text="a", distance=0.1)],
            [WidgetMatch(widget_id=w2, matched_text="b", distance=0.2)],
        ],
        widgets=[_make_widget_record(w1), _make_widget_record(w2)],
        catalog=PrimitiveCatalog(["three-frame"]),
    )

    directives = [
        _directive("w1", intent="first intent"),
        _directive("w2", intent="second intent"),
    ]
    resolutions = await resolver.resolve(directives=directives)

    assert len(resolutions) == 2
    assert [r.ref for r in resolutions] == ["w1", "w2"]
    assert [r.widget_id for r in resolutions] == [w1, w2]
    assert len(repository.calls) == 2


async def test_k_limits_candidates_per_directive() -> None:
    w1 = uuid4()
    resolver, repository, _ = _resolver(
        responses=[[WidgetMatch(widget_id=w1, matched_text="a", distance=0.1)]],
        widgets=[_make_widget_record(w1)],
    )

    directives = [_directive("w1", intent="intent")]
    await resolver.resolve(directives=directives, k=3)

    assert repository.calls[0]["k"] == 3


async def test_default_k_comes_from_settings() -> None:
    w1 = uuid4()
    resolver, repository, _ = _resolver(
        responses=[[WidgetMatch(widget_id=w1, matched_text="a", distance=0.1)]],
        widgets=[_make_widget_record(w1)],
        settings=_settings(max_widgets_per_part=2),
    )

    directives = [_directive("w1", intent="intent")]
    await resolver.resolve(directives=directives)

    assert repository.calls[0]["k"] == 2


async def test_resolved_counter_is_recorded() -> None:
    w1 = uuid4()
    resolver, _, metrics = _resolver(
        responses=[[WidgetMatch(widget_id=w1, matched_text="a", distance=0.1)]],
        widgets=[_make_widget_record(w1)],
    )

    directives = [_directive("w1", intent="intent")]
    await resolver.resolve(directives=directives)

    assert ("widget_resolver.resolved", {}, 1) in metrics.labeled_counters


async def test_widget_record_types_are_preserved() -> None:
    w1 = uuid4()
    resolver, _, _ = _resolver(
        responses=[[WidgetMatch(widget_id=w1, matched_text="d", distance=0.1)]],
        widgets=[_make_widget_record(w1)],
    )

    directives = [_directive("w1", intent="intent")]
    [resolution] = await resolver.resolve(directives=directives)

    assert isinstance(resolution.widget_id, UUID)
    assert isinstance(resolution.candidate, WidgetCandidate)
    assert isinstance(resolution.candidate.distance, float)
