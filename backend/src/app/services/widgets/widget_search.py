"""Search published descriptions of active widgets."""

from src.app.contracts.widgets import WidgetRecord
from src.app.interfaces.repositories.widgets import WidgetRepositoryProtocol


class WidgetSearch:
    def __init__(self, widgets: WidgetRepositoryProtocol) -> None:
        self._widgets = widgets

    async def search(self, embedding: list[float], *, limit: int = 10) -> list[WidgetRecord]:
        return await self._widgets.search_active(embedding, limit)
