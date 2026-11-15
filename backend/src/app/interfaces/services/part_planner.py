"""Contract for splitting parsed documents into generation parts."""

from dataclasses import dataclass
from typing import Protocol

from src.app.contracts.documents import TopicNode


@dataclass(frozen=True, slots=True)
class PartPlan:
    index: int
    title: str
    topic_ids: tuple[str, ...]
    spans: tuple[tuple[int, int], ...]
    tokens: int
    markdown: str


class PartPlanner(Protocol):
    def plan(self, tree: tuple[TopicNode, ...], selected: set[str], markdown: str) -> list[PartPlan]: ...
