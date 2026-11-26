"""SQL of the widget vector search (story 2.3).

One statement with three steps:

1. HNSW takes ``overfetch`` nearest descriptions of active widgets, with
   an optional primitive filter;
2. ``DISTINCT ON (widget_id)`` keeps the best description of each widget;
3. the outer query sorts by distance and returns ``k``.

``hnsw.ef_search`` and ``hnsw.iterative_scan`` are transaction-local and are
set in the same transaction as the SELECT (no commit between them). The
filter by status and primitive runs before the HNSW result is trimmed, which
is why the overfetch exists.
"""

from collections.abc import Sequence

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.contracts.solver.widget_candidate import WidgetMatch
from src.app.contracts.widgets import WidgetStatus
from src.app.interfaces.repositories.widget_search import WidgetSearchRepositoryProtocol
from src.app.models.widget import Widget
from src.app.models.widget_description import WidgetDescription

EF_SEARCH = 100


class WidgetSearchRepository(WidgetSearchRepositoryProtocol):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_nearest_widgets(
        self,
        *,
        query_vector: Sequence[float],
        k: int,
        overfetch: int,
        primitive_id: str | None = None,
    ) -> list[WidgetMatch]:
        if k <= 0 or overfetch <= 0:
            return []
        await self._session.execute(text(f"SET LOCAL hnsw.ef_search = {EF_SEARCH}"))
        await self._session.execute(text("SET LOCAL hnsw.iterative_scan = relaxed_order"))

        distance = WidgetDescription.embedding.cosine_distance(list(query_vector)).label("distance")
        eligible_widget = select(Widget.id).where(
            Widget.id == WidgetDescription.widget_id,
            Widget.status == WidgetStatus.ACTIVE.value,
        )
        if primitive_id is not None:
            eligible_widget = eligible_widget.where(Widget.primitive_id == primitive_id)
        # Keep eligibility as an index-scan filter; flattening EXISTS into a
        # join makes PostgreSQL prefer scanning and sorting the toasted vectors.
        nearest = (
            select(WidgetDescription.widget_id, WidgetDescription.id, WidgetDescription.text, distance)
            .where(eligible_widget.offset(0).exists())
            .order_by(distance)
            .limit(overfetch)
            .subquery("nearest")
        )

        best = (
            select(nearest.c.widget_id, nearest.c.text, nearest.c.distance)
            .distinct(nearest.c.widget_id)
            .order_by(nearest.c.widget_id, nearest.c.distance, nearest.c.id)
            .subquery("best")
        )
        stmt = (
            select(best.c.widget_id, best.c.text, best.c.distance).order_by(best.c.distance, best.c.widget_id).limit(k)
        )
        rows = (await self._session.execute(stmt)).all()
        return [
            WidgetMatch(widget_id=widget_id, matched_text=matched_text, distance=float(distance_value))
            for widget_id, matched_text, distance_value in rows
        ]


__all__ = ["EF_SEARCH", "WidgetSearchRepository"]
