"""Widget search by intent (story 2.3).

The intent is normalised, embedded once and looked up through
``WidgetSearchRepository``. The primitive hint is a soft filter: an unknown
id is ignored, and if the filtered query returns fewer than ``k`` widgets
the search repeats without the filter and fills the tail. Candidates beyond
``SOLVER_SEARCH_MAX_DISTANCE`` are dropped before the reranker of 2.4 sees
them, so an empty neighbourhood costs no cheap-model call.

The service depends on ``EmbeddingServiceInterface`` and on repository
protocols; SQL stays in ``WidgetSearchRepository`` and ORM rows become
``WidgetCandidate`` at the boundary.
"""

import logging
from collections.abc import Callable, Sequence
from time import perf_counter

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.contracts.solver.widget_candidate import WidgetCandidate, WidgetMatch
from src.app.core.settings.solver import SolverSettings
from src.app.exceptions.embeddings import EmbeddingResultMismatchError
from src.app.interfaces.embeddings.embedding_service import EmbeddingServiceInterface
from src.app.interfaces.observability.metrics_collector import MetricsCollector
from src.app.interfaces.repositories.widget_search import WidgetSearchRepositoryProtocol
from src.app.interfaces.repositories.widgets import WidgetRepositoryProtocol
from src.app.repositories.widget_repository import WidgetRepository
from src.app.repositories.widget_search_repository import WidgetSearchRepository
from src.app.services.solver.library.primitive_catalog import PrimitiveCatalog

logger = logging.getLogger(__name__)

_SEARCH_DURATION = "widget_search.duration_seconds"


class WidgetSearch:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        embeddings: EmbeddingServiceInterface,
        catalog: PrimitiveCatalog,
        settings: SolverSettings,
        metrics: MetricsCollector,
        search_repo: Callable[[AsyncSession], WidgetSearchRepositoryProtocol] = WidgetSearchRepository,
        widget_repo: Callable[[AsyncSession], WidgetRepositoryProtocol] = WidgetRepository,
    ) -> None:
        self._session_factory = session_factory
        self._embeddings = embeddings
        self._catalog = catalog
        self._settings = settings
        self._metrics = metrics
        self._search_repo = search_repo
        self._widget_repo = widget_repo

    async def search(
        self,
        intent: str,
        k: int = 5,
        primitive_hint: str | None = None,
    ) -> list[WidgetCandidate]:
        query = " ".join(intent.split())
        if not query or k <= 0:
            return []
        hint = primitive_hint if primitive_hint in self._catalog else None
        vectors = await self._embeddings.embed([query])
        if len(vectors) != 1:
            raise EmbeddingResultMismatchError("Embedding service returned a different number of vectors.")
        vector = vectors[0]

        started = perf_counter()
        try:
            async with self._session_factory() as session:
                repo = self._search_repo(session)
                matches = await repo.find_nearest_widgets(
                    query_vector=vector,
                    k=k,
                    overfetch=self._settings.search_overfetch,
                    primitive_id=hint,
                )
                # Apply the distance threshold before deciding whether the
                # primitive filter left a shortfall: a far filtered match must
                # not occupy a slot that a close unfiltered match could fill.
                matches = self._within_threshold(matches)
                if hint is not None and len(matches) < k:
                    seen = {match.widget_id for match in matches}
                    extra = await repo.find_nearest_widgets(
                        query_vector=vector,
                        k=k,
                        overfetch=self._settings.search_overfetch,
                    )
                    for match in self._within_threshold(extra):
                        if match.widget_id in seen:
                            continue
                        seen.add(match.widget_id)
                        matches.append(match)
                    matches = matches[:k]

                if not matches:
                    return []
                widgets = await self._widget_repo(session).get_many_with_main_description(
                    [match.widget_id for match in matches]
                )
                return [
                    WidgetCandidate.from_match(match, widgets[match.widget_id])
                    for match in matches
                    if match.widget_id in widgets
                ]
        finally:
            self._metrics.observe_histogram(
                _SEARCH_DURATION,
                perf_counter() - started,
                labels={"filtered": "true" if hint is not None else "false"},
            )

    def _within_threshold(self, matches: Sequence[WidgetMatch]) -> list[WidgetMatch]:
        return [match for match in matches if match.distance <= self._settings.search_max_distance]


__all__ = ["WidgetSearch"]
