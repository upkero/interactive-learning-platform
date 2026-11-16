"""Contract for splitting parsed documents into generation parts."""

from typing import Protocol

from src.app.contracts.documents import TopicNode
from src.app.contracts.documents.part_plan import PartPlan


class PartPlanner(Protocol):
    def plan(self, tree: tuple[TopicNode, ...], selected: set[str], markdown: str) -> list[PartPlan]: ...
