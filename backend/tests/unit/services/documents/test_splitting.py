"""Unit tests 1.4.6/1.10: the greedy topic packing rules."""

import pytest

from src.app.exceptions.documents import EmptyTopicSelectionError, UnknownTopicError
from src.app.services.documents.splitting import (
    MAX_TOKENS,
    TAIL_GLUE,
    PlannedPart,
    TopicTreePlanner,
    _Unit,
    pack_units,
)

pytestmark = pytest.mark.unit


def _u(topic_id: str, tokens: int, level: int = 1, title: str | None = None) -> _Unit:
    return _Unit(topic_id=topic_id, title=title or topic_id, level=level, tokens=tokens)


def test_pack_respects_the_maximum() -> None:
    # three units of 9000: 9000+9000 > 22000, so parts of [u1, u2] fail;
    # each part takes one unit
    parts = pack_units([_u("a", 9000), _u("b", 9000), _u("c", 9000)])
    assert [sum(u.tokens for u in part) for part in parts] == [9000, 9000, 9000]


def test_pack_fills_up_to_the_target_and_glues_the_tail() -> None:
    units = [_u(f"t{i}", 7000) for i in range(3)]
    parts = pack_units(units)
    # 7000 + 7000 = 14000 fits; the 7000 tail starts a new part
    assert [sum(u.tokens for u in part) for part in parts] == [14000, 7000]


def test_pack_closes_before_a_new_chapter_after_min_fill() -> None:
    units = [_u("intro", 8000, level=1), _u("ch2", 8000, level=1)]
    parts = pack_units(units)
    # the first part already reached min-fill: the new chapter opens
    # its own part even though 16000 <= max
    assert [sum(u.tokens for u in part) for part in parts] == [8000, 8000]


def test_pack_keeps_a_small_chapter_with_the_current_part() -> None:
    units = [_u("intro", 6000, level=1), _u("note", 2000, level=1)]
    parts = pack_units(units)
    # below min-fill: chapters mix freely
    assert [sum(u.tokens for u in part) for part in parts] == [8000]


def test_pack_glues_a_short_tail_to_the_previous_part() -> None:
    units = [_u("a", 12000), _u("b", 2000)]
    parts = pack_units(units)
    assert len(parts) == 1
    assert sum(u.tokens for u in parts[0]) == 14000


def test_pack_does_not_glue_when_it_would_exceed_the_maximum() -> None:
    units = [_u("a", MAX_TOKENS - 1000), _u("b", TAIL_GLUE - 1000)]
    parts = pack_units(units)
    assert len(parts) == 2


def test_oversized_topic_forms_its_own_part() -> None:
    units = [_u("big", MAX_TOKENS + 500), _u("small", 1000)]
    parts = pack_units(units)
    assert [sum(u.tokens for u in part) for part in parts] == [MAX_TOKENS + 500, 1000]


_TREE = {
    "topics": [
        {
            "id": "a",
            "title": "Adaptive",
            "children": [{"id": "a1", "title": "Chunking", "children": []}],
        },
        {"id": "b", "title": "Quota", "children": []},
    ]
}


def test_plan_rejects_empty_and_unknown_selection() -> None:
    planner = TopicTreePlanner()
    with pytest.raises(EmptyTopicSelectionError) as empty:
        planner.plan(_TREE, [], {})
    assert empty.value.error_code == "empty_topic_selection"

    with pytest.raises(UnknownTopicError) as unknown:
        planner.plan(_TREE, ["a", "nope"], {})
    assert unknown.value.error_code == "unknown_topic"
    assert unknown.value.extra == {"topic_id": "nope"}


def test_plan_packs_selected_topics_in_tree_order() -> None:
    planner = TopicTreePlanner()
    tokens = {"a": 8000, "a1": 7000, "b": 9000}
    plan = planner.plan(_TREE, ["a", "b"], tokens)
    assert [p.index for p in plan.parts] == [0, 1]
    # a (8000) + b (9000) = 17000 <= max, but b is a new chapter after
    # min-fill: separate parts
    assert [p.tokens for p in plan.parts] == [8000, 9000]
    assert [p.topic_ids for p in plan.parts] == [("a",), ("b",)]
    assert plan.parts[0].title == "Adaptive"


def test_plan_child_selection_is_covered_by_the_parent() -> None:
    planner = TopicTreePlanner()
    tokens = {"a": 8000, "a1": 7000, "b": 6000}
    plan = planner.plan(_TREE, ["a", "a1", "b"], tokens)
    # a1 lies inside a's subtree: it must not appear as its own unit
    assert [p.topic_ids for p in plan.parts] == [("a",), ("b",)]
    assert plan.parts[0].tokens == 8000


def test_plan_is_deterministic() -> None:
    planner = TopicTreePlanner()
    tokens = {"a": 8000, "a1": 7000, "b": 9000}
    first = planner.plan(_TREE, ["a", "b"], tokens)
    second = planner.plan(_TREE, ["a", "b"], tokens)
    assert first == second
    assert first.parts == tuple(
        PlannedPart(index=p.index, title=p.title, tokens=p.tokens, topic_ids=p.topic_ids) for p in second.parts
    )
