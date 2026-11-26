"""Widget resolver (story 2.4).

Turns widget directives from the main pass into concrete widget
assignments. For every ``kind="widget"`` directive it searches for
candidates by intent using ``WidgetSearch`` (story 2.3) and picks the
closest one within the distance threshold. Directives without any
candidate are left unresolved.

The primitive hint from the directive is a soft filter: an unknown id is
ignored, and if the filtered search returns no candidates the resolver
falls back to the unfiltered neighbourhood.
"""

import logging
from collections.abc import Sequence
from time import perf_counter

from src.app.contracts.solver.main_pass import MainPassDirective
from src.app.contracts.solver.widget_resolution import WidgetResolution
from src.app.core.settings.solver import SolverSettings
from src.app.interfaces.observability.metrics_collector import MetricsCollector
from src.app.services.solver.library.primitive_catalog import PrimitiveCatalog
from src.app.services.solver.search.widget_search import WidgetSearch

logger = logging.getLogger(__name__)

_RESOLVE_DURATION = "widget_resolver.resolve_duration_seconds"
_RESOLVED_COUNTER = "widget_resolver.resolved"
_UNRESOLVED_COUNTER = "widget_resolver.unresolved"


class WidgetResolver:
    """Resolve widget directives to concrete widgets."""

    def __init__(
        self,
        *,
        search: WidgetSearch,
        catalog: PrimitiveCatalog,
        settings: SolverSettings,
        metrics: MetricsCollector,
    ) -> None:
        self._search = search
        self._catalog = catalog
        self._settings = settings
        self._metrics = metrics

    async def resolve(
        self,
        *,
        directives: Sequence[MainPassDirective],
        k: int | None = None,
    ) -> list[WidgetResolution]:
        """Resolve every widget directive to its best candidate.

        Returns one ``WidgetResolution`` per directive that had at least
        one candidate within the distance threshold. The order of results
        matches the order of the input directives.
        """
        limit = k if k is not None and k > 0 else self._settings.main_pass_max_widgets
        resolutions: list[WidgetResolution] = []
        unresolved = 0

        started = perf_counter()
        try:
            for directive in directives:
                if directive.kind != "widget":
                    continue
                hint = directive.primitive_hint if directive.primitive_hint in self._catalog else None
                candidates = await self._search.search(
                    directive.intent,
                    k=limit,
                    primitive_hint=hint,
                )
                if not candidates:
                    unresolved += 1
                    logger.debug(
                        "No widget candidate for directive %r (intent %r).",
                        directive.ref,
                        directive.intent,
                    )
                    continue
                best = candidates[0]
                resolutions.append(
                    WidgetResolution(
                        ref=directive.ref,
                        widget_id=best.widget_id,
                        candidate=best,
                    )
                )
        finally:
            self._metrics.observe_histogram(
                _RESOLVE_DURATION,
                perf_counter() - started,
            )
            self._metrics.increment_counter(_RESOLVED_COUNTER, by=len(resolutions))
            self._metrics.increment_counter(_UNRESOLVED_COUNTER, by=unresolved)

        return resolutions


__all__ = ["WidgetResolver"]
