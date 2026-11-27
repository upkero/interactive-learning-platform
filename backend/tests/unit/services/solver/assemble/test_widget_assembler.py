"""Unit tests of the widget assembler (story 2.5)."""

from collections.abc import Sequence
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import JsonValue
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.contracts.solver.widget_assembly import WidgetAssembly
from src.app.contracts.solver.widget_candidate import WidgetCandidate
from src.app.contracts.solver.widget_resolution import WidgetResolution
from src.app.contracts.widgets import UsageStatus, WidgetKind, WidgetUsageDraft, WidgetUsageRecord
from src.app.core.settings.solver import SolverSettings
from src.app.services.solver.assemble.widget_assembler import WidgetAssembler
from tests.support.fakes.db.session import FakeSession
from tests.support.fakes.observability.metrics_collector import RecordingMetricsCollector
from tests.support.fakes.repositories.widgets import FakeWidgetUsageRepository

pytestmark = pytest.mark.unit


def _candidate(widget_id: UUID, params: dict[str, JsonValue] | None = None, distance: float = 0.1) -> WidgetCandidate:
    return WidgetCandidate(
        widget_id=widget_id,
        kind=WidgetKind.CONFIG,
        primitive_id="three-frame",
        mode="explore",
        params=params,
        matched_text="matched description",
        description="Main description",
        distance=distance,
    )


def _resolution(widget_id: UUID, ref: str = "w1", params: dict[str, JsonValue] | None = None) -> WidgetResolution:
    return WidgetResolution(
        ref=ref,
        widget_id=widget_id,
        candidate=_candidate(widget_id, params=params),
    )


class ScriptedWidgetUsageRepository(FakeWidgetUsageRepository):
    """Records calls and returns usage records in draft order."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[tuple[UUID, list[WidgetUsageDraft]]] = []

    async def add_many(self, part_id: UUID, usages: Sequence[WidgetUsageDraft]) -> list[WidgetUsageRecord]:
        self.calls.append((part_id, list(usages)))
        return await super().add_many(part_id, usages)


def _assembler(
    *,
    metrics: RecordingMetricsCollector | None = None,
    session: FakeSession | None = None,
) -> tuple[WidgetAssembler, ScriptedWidgetUsageRepository, RecordingMetricsCollector]:
    repository = ScriptedWidgetUsageRepository()
    collector = metrics or RecordingMetricsCollector()
    session_factory = cast(async_sessionmaker[AsyncSession], lambda: session or FakeSession())
    assembler = WidgetAssembler(
        session_factory=session_factory,
        widget_usages=lambda _session: repository,
        settings=SolverSettings(_env_file=None),
        metrics=collector,
    )
    return assembler, repository, collector


async def test_assemble_creates_one_usage_per_resolution() -> None:
    w1 = uuid4()
    w2 = uuid4()
    part_id = uuid4()
    session = FakeSession()
    assembler, repository, _ = _assembler(session=session)

    resolutions = [_resolution(w1, "w1", {"a": 1}), _resolution(w2, "w2", {"b": 2})]
    assembly = await assembler.assemble(part_id=part_id, resolutions=resolutions)

    assert isinstance(assembly, WidgetAssembly)
    assert assembly.part_id == part_id
    assert len(assembly.placements) == 2
    assert [p.ref for p in assembly.placements] == ["w1", "w2"]
    assert all(isinstance(p.usage_id, UUID) for p in assembly.placements)
    assert session.committed == 1

    [call] = repository.calls
    assert call[0] == part_id
    drafts = call[1]
    assert len(drafts) == 2
    assert drafts[0].directive_ref == "w1"
    assert drafts[0].position == 0
    assert drafts[0].widget_id == w1
    assert drafts[0].params == {"a": 1}
    assert drafts[0].status is UsageStatus.PENDING
    assert drafts[1].directive_ref == "w2"
    assert drafts[1].position == 1
    assert drafts[1].widget_id == w2
    assert drafts[1].params == {"b": 2}


async def test_empty_resolutions_returns_empty_assembly_without_db() -> None:
    part_id = uuid4()
    assembler, repository, metrics = _assembler()

    assembly = await assembler.assemble(part_id=part_id, resolutions=[])

    assert assembly == WidgetAssembly(part_id=part_id, placements=())
    assert repository.calls == []
    assert metrics.counters == []


async def test_params_none_is_passed_through() -> None:
    w1 = uuid4()
    part_id = uuid4()
    assembler, repository, _ = _assembler()

    resolutions = [_resolution(w1, "w1", None)]
    await assembler.assemble(part_id=part_id, resolutions=resolutions)

    [call] = repository.calls
    assert call[1][0].params is None


async def test_placement_order_matches_input_order() -> None:
    w1 = uuid4()
    w2 = uuid4()
    w3 = uuid4()
    part_id = uuid4()
    assembler, _, _ = _assembler()

    resolutions = [_resolution(w3, "w3"), _resolution(w1, "w1"), _resolution(w2, "w2")]
    assembly = await assembler.assemble(part_id=part_id, resolutions=resolutions)

    assert [p.ref for p in assembly.placements] == ["w3", "w1", "w2"]


async def test_metrics_are_recorded() -> None:
    w1 = uuid4()
    part_id = uuid4()
    assembler, _, metrics = _assembler()

    resolutions = [_resolution(w1, "w1")]
    await assembler.assemble(part_id=part_id, resolutions=resolutions)

    assert ("widget_assembler.placed", {}, 1) in metrics.labeled_counters
    assert ("widget_assembler.skipped", {}, 0) in metrics.labeled_counters
    assert len(metrics.histograms_named("widget_assembler.assemble_duration_seconds")) == 1


async def test_usage_id_type_is_uuid() -> None:
    w1 = uuid4()
    part_id = uuid4()
    assembler, _, _ = _assembler()

    resolutions = [_resolution(w1, "w1")]
    [placement] = (await assembler.assemble(part_id=part_id, resolutions=resolutions)).placements

    assert isinstance(placement.usage_id, UUID)
