"""Part planner backed by deterministic splitting of the source Markdown."""

from src.app.contracts.documents import TopicNode
from src.app.contracts.documents.part_plan import PartPlan
from src.app.ingest.splitting import SplitLimits, split_document
from src.app.ingest.tokens import TokenCounting


class DocumentPartPlanner:
    def __init__(self, counter: TokenCounting, limits: SplitLimits) -> None:
        self._counter = counter
        self._limits = limits

    def plan(self, tree: tuple[TopicNode, ...], selected: set[str], markdown: str) -> list[PartPlan]:
        return split_document(tree, selected, markdown, self._counter, self._limits)
