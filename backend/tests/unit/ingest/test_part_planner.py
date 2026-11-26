"""The document part planner selects complete subtrees in document order."""

import pytest

from src.app.contracts.documents import TopicNode
from src.app.ingest.part_planner import DocumentPartPlanner
from src.app.ingest.splitting import SplitLimits
from src.app.ingest.tokens import TokenCounter

pytestmark = pytest.mark.unit


def test_selected_subtrees_are_ordered_and_not_duplicated() -> None:
    child = TopicNode(id="1.1", title="Child", level=2, start=2, end=4, own_tokens=2, total_tokens=2)
    root = TopicNode(id="1", title="Root", level=1, start=0, end=4, own_tokens=2, total_tokens=4, children=(child,))
    other = TopicNode(id="2", title="Other", level=1, start=4, end=6, own_tokens=2, total_tokens=2)
    planner = DocumentPartPlanner(TokenCounter(), SplitLimits(15_000, 22_000))
    parts = planner.plan((root, other), {"2", "1", "1.1"}, "abcdef")
    assert [(p.index, p.title, p.markdown, p.spans, p.tokens) for p in parts] == [
        (0, "Root — Other", "abcdef", ((0, 4), (4, 6)), 2),
    ]
    assert planner.plan((root, other), {"1.1"}, "abcdef")[0].markdown == "cd"
