"""Output contracts of the widget resolver (story 2.4).

The resolver turns widget directives from the main pass into concrete
widget assignments: one ``WidgetResolution`` per directive that could be
filled, mapping the directive ``ref`` to the chosen widget and the
candidate that was selected.
"""

from dataclasses import dataclass
from uuid import UUID

from src.app.contracts.solver.widget_candidate import WidgetCandidate


@dataclass(frozen=True, slots=True)
class WidgetResolution:
    """One widget directive resolved to a concrete widget.

    ``ref`` names the directive slot (e.g. ``w1``). ``widget_id`` is the
    widget that fills it. ``candidate`` is the search result that was
    chosen, including its distance and matched description.
    """

    ref: str
    widget_id: UUID
    candidate: WidgetCandidate


__all__ = ["WidgetResolution"]
