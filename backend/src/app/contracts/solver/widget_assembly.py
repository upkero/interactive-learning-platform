"""Output contracts of the widget assembler (story 2.5).

The assembler turns resolved widget assignments into persisted widget
usage records on a document part. Each ``WidgetPlacement`` names the
directive slot that was filled and the usage row that was created.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class WidgetPlacement:
    """One widget directive assembled into a part usage.

    ``ref`` names the directive slot (e.g. ``w1``). ``usage_id`` is the
    persisted ``widget_usages`` row that links the widget to the part.
    """

    ref: str
    usage_id: UUID


@dataclass(frozen=True, slots=True)
class WidgetAssembly:
    """Result of assembling widget resolutions into a part.

    ``placements`` holds one entry per resolved directive, in the same
    order as the input resolutions. ``part_id`` names the part the
    usages belong to.
    """

    part_id: UUID
    placements: tuple[WidgetPlacement, ...]


__all__ = ["WidgetAssembly", "WidgetPlacement"]
