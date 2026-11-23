"""Production planner for deterministic document splitting."""

from src.app.contracts.documents import TopicNode
from src.app.contracts.documents.part_plan import PartPlan
from src.app.core.settings.ingest import IngestSettings
from src.app.ingest.splitting import SplitLimits, split_document
from src.app.ingest.tokens import TokenCounter


class TopicPerPartPlanner:
    def __init__(self, *, counter: TokenCounter | None = None, settings: IngestSettings | None = None) -> None:
        self._counter = counter or TokenCounter()
        config = settings or IngestSettings()
        self._limits = SplitLimits(config.split_target_tokens, config.split_max_tokens)

    def plan(self, tree: tuple[TopicNode, ...], selected: set[str], markdown: str) -> list[PartPlan]:
        return split_document(tree, selected, markdown, self._counter, self._limits)
