"""Protocol of the vector search repository (story 2.3)."""

from collections.abc import Sequence
from typing import Protocol

from src.app.contracts.solver.widget_candidate import WidgetMatch


class WidgetSearchRepositoryProtocol(Protocol):
    """One SQL statement: nearest descriptions of active widgets."""

    async def find_nearest_widgets(
        self,
        *,
        query_vector: Sequence[float],
        k: int,
        overfetch: int,
        primitive_id: str | None = None,
    ) -> list[WidgetMatch]: ...


__all__ = ["WidgetSearchRepositoryProtocol"]
