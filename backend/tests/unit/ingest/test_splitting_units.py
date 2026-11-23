"""Topic-tree flattening and text-boundary tests."""

from typing import cast

import pytest

from src.app.contracts.documents import TopicNode
from src.app.ingest.splitting import SplitLimits, collect_units, split_by_paragraphs, split_document
from src.app.ingest.tokens import TokenCounter

pytestmark = pytest.mark.unit


class FakeCounter:
    def count(self, text: str) -> int:
        return len(text.split())

    def encode(self, text: str) -> list[int]:
        return list(range(len(text.split())))

    def decode(self, tokens: list[int]) -> str:
        return "x " * len(tokens)


COUNTER = cast(TokenCounter, FakeCounter())


def node(node_id: str, title: str, start: int, end: int, total: int, children: tuple[TopicNode, ...] = ()) -> TopicNode:
    return TopicNode(node_id, title, 1, start, end, total, total, children=children)


def test_selected_parent_includes_subtree_once() -> None:
    child = node("1.1", "Child", 9, 18, 9)
    root = node("1", "Root", 0, 18, 18, (child,))
    plans = split_document((root,), {"1", "1.1"}, "root text child text", COUNTER, SplitLimits(10, 20))
    assert [plan.topic_ids for plan in plans] == [("1",)]


def test_large_topic_is_split_on_paragraphs() -> None:
    markdown = "one two three\n\nfour five six\n\nseven eight nine"
    root = node("1", "Large", 0, len(markdown), 30)
    units = collect_units((root,), {"1"}, markdown, COUNTER, SplitLimits(5, 8))
    assert [(markdown[unit.start : unit.end], unit.tokens) for unit in units] == [
        ("one two three\n\n", 3),
        ("four five six\n\n", 3),
        ("seven eight nine", 3),
    ]


def test_image_directive_stays_with_previous_paragraph() -> None:
    markdown = 'paragraph text\n\n::image{id="img_1"}\n\nnext text'
    spans = split_by_paragraphs(markdown, 0, len(markdown), COUNTER, SplitLimits(3, 8))
    assert markdown[spans[0][0] : spans[0][1]].endswith('::image{id="img_1"}\n\n')


def test_empty_selection_has_no_parts() -> None:
    root = node("1", "Root", 0, 4, 1)
    assert split_document((root,), set(), "text", COUNTER, SplitLimits(10, 20)) == []
