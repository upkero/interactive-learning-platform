"""Widget assembler (story 2.5).

Turns resolved widget assignments from the resolver into persisted widget
usage records on a document part. Each ``WidgetResolution`` becomes one
``WidgetUsageDraft`` (directive slot → widget, with the widget's params
and a sequential page position) and is written through
``WidgetUsageRepository``.

The assembler runs in the ``ASSEMBLING`` pipeline stage, right after the
resolver (2.4) has filled the directive slots produced by the main pass
(2.2).
"""

import logging
from collections.abc import Callable, Sequence
from time import perf_counter
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.contracts.solver.widget_assembly import WidgetAssembly, WidgetPlacement
from src.app.contracts.solver.widget_resolution import WidgetResolution
from src.app.contracts.widgets import UsageStatus, WidgetUsageDraft
from src.app.core.settings.solver import SolverSettings
from src.app.interfaces.observability.metrics_collector import MetricsCollector
from src.app.interfaces.repositories.widgets import WidgetUsageRepositoryProtocol
from src.app.repositories.widget_usage_repository import WidgetUsageRepository

logger = logging.getLogger(__name__)

_ASSEMBLE_DURATION = "widget_assembler.assemble_duration_seconds"
_PLACED_COUNTER = "widget_assembler.placed"
_SKIPPED_COUNTER = "widget_assembler.skipped"


class WidgetAssembler:
    """Assemble resolved widgets into part usages."""

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        widget_usages: Callable[[AsyncSession], WidgetUsageRepositoryProtocol] = WidgetUsageRepository,
        settings: SolverSettings,
        metrics: MetricsCollector,
    ) -> None:
        self._session_factory = session_factory
        self._widget_usages = widget_usages
        self._settings = settings
        self._metrics = metrics

    async def assemble(
        self,
        *,
        part_id: UUID,
        resolutions: Sequence[WidgetResolution],
    ) -> WidgetAssembly:
        """Persist one usage per resolved widget directive.

        Returns a ``WidgetAssembly`` with one ``WidgetPlacement`` per
        resolution, preserving input order. Empty input yields an empty
        assembly without touching the database.
        """
        if not resolutions:
            return WidgetAssembly(part_id=part_id, placements=())

        started = perf_counter()
        try:
            async with self._session_factory() as session:
                repo = self._widget_usages(session)
                drafts = [
                    WidgetUsageDraft(
                        directive_ref=resolution.ref,
                        position=index,
                        widget_id=resolution.widget_id,
                        params=resolution.candidate.params,
                        status=UsageStatus.PENDING,
                    )
                    for index, resolution in enumerate(resolutions)
                ]
                records = await repo.add_many(part_id, drafts)
        finally:
            self._metrics.observe_histogram(_ASSEMBLE_DURATION, perf_counter() - started)

        placements = tuple(WidgetPlacement(ref=record.directive_ref, usage_id=record.id) for record in records)
        placed = len(placements)
        skipped = len(resolutions) - placed
        self._metrics.increment_counter(_PLACED_COUNTER, by=placed)
        self._metrics.increment_counter(_SKIPPED_COUNTER, by=skipped)

        logger.info(
            "Widget assembly completed.",
            extra={
                "part_id": str(part_id),
                "directives": len(resolutions),
                "placed": placed,
                "skipped": skipped,
            },
        )
        return WidgetAssembly(part_id=part_id, placements=placements)


__all__ = ["WidgetAssembler"]
