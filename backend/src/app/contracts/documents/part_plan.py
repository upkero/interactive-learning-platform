"""One planned generation part."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PartPlan:
    index: int
    title: str
    topic_ids: tuple[str, ...]
    spans: tuple[tuple[int, int], ...]
    tokens: int
    markdown: str
