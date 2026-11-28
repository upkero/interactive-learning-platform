"""Unit tests of widget search by intent (story 2.3)."""

import inspect
from collections.abc import Sequence
from typing import cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.bootstrap.container import ApplicationContainer
from src.app.contracts.solver.widget_candidate import WidgetMatch
from src.app.contracts.widgets import WidgetKind, WidgetRecord
from src.app.core.settings.solver import SolverSettings
from src.app.exceptions.embeddings import EmbeddingResultMismatchError
from src.app.interfaces.embeddings.embedding_service import EmbeddingServiceInterface
from src.app.interfaces.repositories.widget_search import WidgetSearchRepositoryProtocol
from src.app.repositories.primitive_repository import PrimitiveRepository
from src.app.repositories.widget_repository import WidgetRepository
from src.app.repositories.widget_search_repository import WidgetSearchRepository
from src.app.services.solver.library.primitive_catalog import PrimitiveCatalog
from src.app.services.solver.search.widget_search import WidgetSearch
from tests.support.fakes.observability.metrics_collector import RecordingMetricsCollector
from tests.support.fakes.repositories.widgets import FakePrimitiveRepository, FakeWidgetRepository


class FakeSession:
    async def __aenter__(self) -> "FakeSession":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None


class FakeEmbeddingService(EmbeddingServiceInterface):
    def __init__(self, vectors: list[list[float]] | None = None) -> None:
        self.vectors = vectors if vectors is not None else [[0.1, 0.2, 0.3, 0.4]]
        self.calls: list[list[str]] = []

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return self.vectors


class ScriptedSearchRepository(WidgetSearchRepositoryProtocol):
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


def _settings(**overrides: object) -> SolverSettings:
    values: dict[str, object] = {"search_overfetch": 40, "search_max_distance": 0.55}
    values.update(overrides)
    return SolverSettings(_env_file=None, **values)  # type: ignore[arg-type]


def _search(
    *,
    widgets: FakeWidgetRepository,
    embeddings: FakeEmbeddingService,
    responses: list[list[WidgetMatch]],
    catalog: PrimitiveCatalog | None = None,
    settings: SolverSettings | None = None,
    metrics: RecordingMetricsCollector | None = None,
) -> tuple[WidgetSearch, ScriptedSearchRepository, RecordingMetricsCollector]:
    repository = ScriptedSearchRepository(responses)
    primitives = FakePrimitiveRepository()
    collector = metrics or RecordingMetricsCollector()
    session_factory = cast(async_sessionmaker[AsyncSession], lambda: FakeSession())
    search = WidgetSearch(
        session_factory=session_factory,
        embeddings=embeddings,
        catalog=catalog or PrimitiveCatalog(),
        settings=settings or _settings(),
        metrics=collector,
        search_repo=lambda _session: repository,
        widget_repo=lambda _session: widgets,
        primitive_repo=lambda _session: primitives,
    )
    return search, repository, collector


async def _widget(
    repository: FakeWidgetRepository,
    *,
    primitive_id: str | None = "three-frame",
    mode: str = "explore",
) -> WidgetRecord:
    return await repository.create(
        kind=WidgetKind.CONFIG,
        primitive_id=primitive_id,
        mode=mode,
        params={},
    )


async def test_search_normalises_intent_and_returns_candidates() -> None:
    widgets = FakeWidgetRepository()
    first = await _widget(widgets, primitive_id="three-frame")
    second = await _widget(widgets, primitive_id="key-terms")
    embeddings = FakeEmbeddingService()
    search, repository, metrics = _search(
        widgets=widgets,
        embeddings=embeddings,
        responses=[
            [
                WidgetMatch(widget_id=first.id, matched_text="closest description", distance=0.2),
                WidgetMatch(widget_id=second.id, matched_text="other description", distance=0.4),
            ]
        ],
        catalog=PrimitiveCatalog(["three-frame"]),
    )

    candidates = await search.search("  show   the\nweight  ", k=2, primitive_hint="three-frame")

    assert embeddings.calls == [["show the weight"]]
    assert repository.calls == [
        {
            "query_vector": [0.1, 0.2, 0.3, 0.4],
            "k": 2,
            "overfetch": 40,
            "primitive_id": "three-frame",
        }
    ]
    assert [candidate.widget_id for candidate in candidates] == [first.id, second.id]
    assert candidates[0].kind is WidgetKind.CONFIG
    assert candidates[0].primitive_id == "three-frame"
    assert candidates[0].mode == "explore"
    assert candidates[0].params == {}
    assert candidates[0].matched_text == "closest description"
    assert candidates[0].description == f"Main description of {first.id}"
    assert candidates[0].distance == 0.2
    histograms = metrics.histograms_named("widget_search.duration_seconds")
    assert len(histograms) == 1
    assert histograms[0].labels == {"filtered": "true"}


async def test_unknown_primitive_hint_is_ignored() -> None:
    widgets = FakeWidgetRepository()
    widget = await _widget(widgets)
    search, repository, metrics = _search(
        widgets=widgets,
        embeddings=FakeEmbeddingService(),
        responses=[[WidgetMatch(widget_id=widget.id, matched_text="d", distance=0.1)]],
        catalog=PrimitiveCatalog(["three-frame"]),
    )

    await search.search("intent", primitive_hint="no-such-primitive")

    assert repository.calls[0]["primitive_id"] is None
    assert metrics.histograms_named("widget_search.duration_seconds")[0].labels == {"filtered": "false"}


async def test_short_filtered_result_is_filled_without_filter() -> None:
    widgets = FakeWidgetRepository()
    first = await _widget(widgets, primitive_id="three-frame")
    second = await _widget(widgets, primitive_id="key-terms")
    third = await _widget(widgets, primitive_id="key-terms")
    search, repository, _ = _search(
        widgets=widgets,
        embeddings=FakeEmbeddingService(),
        responses=[
            [WidgetMatch(widget_id=first.id, matched_text="a", distance=0.2)],
            [
                WidgetMatch(widget_id=first.id, matched_text="a", distance=0.2),
                WidgetMatch(widget_id=second.id, matched_text="b", distance=0.3),
                WidgetMatch(widget_id=third.id, matched_text="c", distance=0.4),
            ],
        ],
        catalog=PrimitiveCatalog(["three-frame"]),
    )

    candidates = await search.search("intent", k=3, primitive_hint="three-frame")

    assert [call["primitive_id"] for call in repository.calls] == ["three-frame", None]
    assert [candidate.widget_id for candidate in candidates] == [first.id, second.id, third.id]
    assert len({candidate.widget_id for candidate in candidates}) == 3


async def test_far_filtered_match_does_not_block_fallback() -> None:
    widgets = FakeWidgetRepository()
    far = await _widget(widgets, primitive_id="three-frame")
    near = await _widget(widgets, primitive_id="key-terms")
    search, repository, _ = _search(
        widgets=widgets,
        embeddings=FakeEmbeddingService(),
        responses=[
            [WidgetMatch(widget_id=far.id, matched_text="far", distance=0.9)],
            [
                WidgetMatch(widget_id=far.id, matched_text="far", distance=0.9),
                WidgetMatch(widget_id=near.id, matched_text="near", distance=0.2),
            ],
        ],
        catalog=PrimitiveCatalog(["three-frame"]),
    )

    candidates = await search.search("intent", k=2, primitive_hint="three-frame")

    assert [call["primitive_id"] for call in repository.calls] == ["three-frame", None]
    assert [candidate.widget_id for candidate in candidates] == [near.id]


@pytest.mark.parametrize(("override", "threshold"), [(None, 0.4449), ("0.6", 0.6)], ids=["bge-default", "env-override"])
async def test_threshold_is_inclusive_and_applied_before_enrichment(
    monkeypatch: pytest.MonkeyPatch, override: str | None, threshold: float
) -> None:
    if override is None:
        monkeypatch.delenv("SOLVER_SEARCH_MAX_DISTANCE", raising=False)
    else:
        monkeypatch.setenv("SOLVER_SEARCH_MAX_DISTANCE", override)
    widgets = FakeWidgetRepository()
    included = await _widget(widgets)
    too_far = await _widget(widgets)
    search, _, _ = _search(
        widgets=widgets,
        embeddings=FakeEmbeddingService(),
        responses=[
            [
                WidgetMatch(widget_id=included.id, matched_text="edge", distance=threshold),
                WidgetMatch(widget_id=too_far.id, matched_text="far", distance=threshold + 0.0000001),
            ]
        ],
        settings=SolverSettings(_env_file=None),
    )

    candidates = await search.search("intent")

    assert [candidate.widget_id for candidate in candidates] == [included.id]


async def test_no_candidates_within_threshold_returns_empty() -> None:
    widgets = FakeWidgetRepository()
    far = await _widget(widgets)
    search, _, _ = _search(
        widgets=widgets,
        embeddings=FakeEmbeddingService(),
        responses=[[WidgetMatch(widget_id=far.id, matched_text="far", distance=1.2)]],
    )

    assert await search.search("intent") == []


async def test_empty_intent_or_non_positive_k_skips_all_dependencies() -> None:
    widgets = FakeWidgetRepository()
    embeddings = FakeEmbeddingService()
    search, repository, metrics = _search(widgets=widgets, embeddings=embeddings, responses=[])

    assert await search.search("   ", k=5) == []
    assert await search.search("intent", k=0) == []
    assert await search.search("intent", k=-1) == []
    assert embeddings.calls == []
    assert repository.calls == []
    assert metrics.histograms == []


async def test_embedding_result_count_mismatch_is_rejected() -> None:
    widgets = FakeWidgetRepository()
    embeddings = FakeEmbeddingService(vectors=[])
    search, repository, _ = _search(widgets=widgets, embeddings=embeddings, responses=[])

    with pytest.raises(EmbeddingResultMismatchError):
        await search.search("intent")

    assert repository.calls == []


async def test_missing_widget_is_skipped() -> None:
    widgets = FakeWidgetRepository()
    missing = uuid4()
    search, _, metrics = _search(
        widgets=widgets,
        embeddings=FakeEmbeddingService(),
        responses=[[WidgetMatch(widget_id=missing, matched_text="d", distance=0.1)]],
    )

    assert await search.search("intent") == []
    assert len(metrics.histograms_named("widget_search.duration_seconds")) == 1


async def test_known_hint_with_enough_results_does_not_fall_back() -> None:
    widgets = FakeWidgetRepository()
    widget = await _widget(widgets)
    search, repository, _ = _search(
        widgets=widgets,
        embeddings=FakeEmbeddingService(),
        responses=[[WidgetMatch(widget_id=widget.id, matched_text="d", distance=0.1)]],
        catalog=PrimitiveCatalog(["three-frame"]),
    )

    await search.search("intent", k=1, primitive_hint="three-frame")

    assert len(repository.calls) == 1


async def test_k_larger_than_results_returns_all_available() -> None:
    widgets = FakeWidgetRepository()
    first = await _widget(widgets)
    second = await _widget(widgets)
    search, _, _ = _search(
        widgets=widgets,
        embeddings=FakeEmbeddingService(),
        responses=[
            [
                WidgetMatch(widget_id=first.id, matched_text="a", distance=0.1),
                WidgetMatch(widget_id=second.id, matched_text="b", distance=0.2),
            ]
        ],
    )

    candidates = await search.search("intent", k=10)

    assert [candidate.widget_id for candidate in candidates] == [first.id, second.id]


async def test_fallback_deduplicates_widget_ids() -> None:
    widgets = FakeWidgetRepository()
    first = await _widget(widgets)
    second = await _widget(widgets)
    search, _, _ = _search(
        widgets=widgets,
        embeddings=FakeEmbeddingService(),
        responses=[
            [WidgetMatch(widget_id=first.id, matched_text="a", distance=0.1)],
            [
                WidgetMatch(widget_id=second.id, matched_text="b", distance=0.2),
                WidgetMatch(widget_id=second.id, matched_text="b", distance=0.2),
            ],
        ],
        catalog=PrimitiveCatalog(["three-frame"]),
    )

    candidates = await search.search("intent", k=3, primitive_hint="three-frame")

    assert [candidate.widget_id for candidate in candidates] == [first.id, second.id]


async def test_widget_record_ids_are_preserved() -> None:
    widgets = FakeWidgetRepository()
    widget = await _widget(widgets)
    search, _, _ = _search(
        widgets=widgets,
        embeddings=FakeEmbeddingService(),
        responses=[[WidgetMatch(widget_id=widget.id, matched_text="d", distance=0.1)]],
    )

    [candidate] = await search.search("intent")

    assert isinstance(candidate.widget_id, UUID)
    assert candidate.widget_id == widget.id


def test_repository_factories_are_explicit_required_dependencies() -> None:
    parameters = inspect.signature(WidgetSearch).parameters

    for name in ("search_repo", "widget_repo", "primitive_repo"):
        assert parameters[name].default is inspect.Parameter.empty


def test_application_container_wires_concrete_repository_factories() -> None:
    search = ApplicationContainer().widget_search

    assert search._search_repo is WidgetSearchRepository
    assert search._widget_repo is WidgetRepository
    assert search._primitive_repo is PrimitiveRepository
