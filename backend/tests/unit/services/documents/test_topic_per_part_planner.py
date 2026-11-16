"""The temporary planner selects complete subtrees in document order."""

import pytest

from src.app.contracts.documents import TopicNode
from src.app.services.documents.topic_per_part_planner import TopicPerPartPlanner

pytestmark = pytest.mark.unit


def test_selected_subtrees_are_ordered_and_not_duplicated() -> None:
    child = TopicNode(id="1.1", title="Child", level=2, start=2, end=4, own_tokens=2, total_tokens=2)
    root = TopicNode(id="1", title="Root", level=1, start=0, end=4, own_tokens=2, total_tokens=4, children=(child,))
    other = TopicNode(id="2", title="Other", level=1, start=4, end=6, own_tokens=2, total_tokens=2)
    planner = TopicPerPartPlanner()
    parts = planner.plan((root, other), {"2", "1", "1.1"}, "abcdef")
    assert [(p.index, p.title, p.tokens, p.markdown, p.spans) for p in parts] == [
        (0, "Root", 4, "abcd", ((0, 4),)),
        (1, "Other", 2, "ef", ((4, 6),)),
    ]
    assert planner.plan((root, other), {"1.1"}, "abcdef")[0].markdown == "cd"
