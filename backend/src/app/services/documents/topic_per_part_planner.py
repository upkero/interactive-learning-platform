"""Temporary 1.10 planner: one part per selected subtree."""

from src.app.contracts.documents import TopicNode
from src.app.contracts.documents.part_plan import PartPlan


class TopicPerPartPlanner:
    def plan(self, tree: tuple[TopicNode, ...], selected: set[str], markdown: str) -> list[PartPlan]:
        result: list[PartPlan] = []

        def visit(node: TopicNode) -> None:
            if node.id in selected:
                result.append(
                    PartPlan(
                        len(result),
                        node.title,
                        (node.id,),
                        ((node.start, node.end),),
                        node.total_tokens,
                        markdown[node.start : node.end],
                    )
                )
                return
            for child in node.children:
                visit(child)

        for root in tree:
            visit(root)
        return result
