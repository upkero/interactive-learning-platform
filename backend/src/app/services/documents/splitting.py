"""Topic-level part planning for the generation preview (story 1.4.6).

Implements the greedy packing rules of story 1.10 (``pack_units``) at
the topic granularity available before the parse pipeline exists: the
units are selected topics with their subtree token sums, and the same
thresholds apply — target 15000, maximum 22000, chapter break at
min-fill 7500 and tail gluing below 5000.

The function is pure and deterministic: two identical selections always
produce the same preview, and nothing is written anywhere.
"""

from dataclasses import dataclass
from typing import Any

from src.app.exceptions.documents import EmptyTopicSelectionError, UnknownTopicError

TARGET_TOKENS = 15_000
MAX_TOKENS = 22_000
MIN_FILL = TARGET_TOKENS // 2  # 7500: close a part before a new chapter
TAIL_GLUE = TARGET_TOKENS // 3  # 5000: glue a short tail to the previous part


@dataclass(frozen=True, slots=True)
class PlannedPart:
    """One prospective page of the conspectus (preview, not persisted)."""

    index: int
    title: str
    tokens: int
    topic_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TopicPlan:
    parts: tuple[PlannedPart, ...]


@dataclass(frozen=True, slots=True)
class _Unit:
    topic_id: str
    title: str
    level: int
    tokens: int


def _flatten(
    node: dict[str, Any],
    level: int,
    *,
    selected: frozenset[str],
    covered: set[str],
    units: list[_Unit],
) -> None:
    """Depth-first walk, keeping only selected topics not covered by an ancestor."""
    topic_id = str(node["id"])
    subtree = _subtree_ids(node)
    # keep a topic only when none of its subtree is already covered by
    # a selected ancestor: otherwise the tokens would count twice
    if topic_id in selected and not (subtree & covered):
        covered |= subtree
        units.append(
            _Unit(
                topic_id=topic_id,
                title=str(node["title"]),
                level=level,
                tokens=int(node.get("tokens", 0)),
            )
        )
    for child in node.get("children", []):
        _flatten(child, level + 1, selected=selected, covered=covered, units=units)


def _subtree_ids(node: dict[str, Any]) -> set[str]:
    ids = {str(node["id"])}
    for child in node.get("children", []):
        ids |= _subtree_ids(child)
    return ids


def pack_units(
    units: list[_Unit],
    *,
    target: int = TARGET_TOKENS,
    maximum: int = MAX_TOKENS,
    min_fill: int = MIN_FILL,
    tail_glue: int = TAIL_GLUE,
) -> list[list[_Unit]]:
    """Greedy packing of ordered units into parts (story 1.10.1).

    Rules: close a part when adding a unit would exceed the maximum,
    close before a level-1 chapter once the part reached min-fill, and
    glue a short last part (below the glue threshold) to the previous
    one when the sum stays within the maximum. An oversized unit (> max)
    forms its own part: content-level splitting is the worker's job.
    """
    parts: list[list[_Unit]] = []
    current: list[_Unit] = []
    current_tokens = 0

    def close() -> None:
        nonlocal current, current_tokens
        if current:
            parts.append(current)
            current = []
            current_tokens = 0

    for unit in units:
        if unit.tokens > maximum:
            close()
            parts.append([unit])
            continue
        if current and unit.level == 1 and current_tokens >= min_fill:
            close()  # do not mix different chapters
        if current and current_tokens + unit.tokens > maximum:
            close()
        current.append(unit)
        current_tokens += unit.tokens
    close()

    if len(parts) >= 2:
        last = parts[-1]
        last_tokens = sum(u.tokens for u in last)
        previous = parts[-2]
        if last_tokens < tail_glue and last_tokens + sum(u.tokens for u in previous) <= maximum:
            parts.pop()
            parts[-1] = previous + last
    return parts


class TopicTreePlanner:
    """Builds the part preview from the topic tree and token sums.

    ``tokens_by_topic`` holds the subtree token sum of every topic
    (the same accounting as the topics read endpoint: a part counts
    once towards every topic whose subtree it touches). The selection
    becomes disjoint through the ancestor-coverage rule, so the unit
    tokens never overlap.
    """

    def plan(
        self,
        topic_tree: dict[str, Any],
        topic_ids: list[str],
        tokens_by_topic: dict[str, int],
    ) -> TopicPlan:
        if not topic_ids:
            raise EmptyTopicSelectionError()

        selected = frozenset(topic_ids)
        unknown = selected - _all_topic_ids(topic_tree)
        if unknown:
            raise UnknownTopicError(extra={"topic_id": sorted(unknown)[0]})

        roots = topic_tree.get("topics", [])
        # the caller passes per-topic subtree sums; annotate every node
        for root in roots:
            _annotate_tokens(root, tokens_by_topic)

        units: list[_Unit] = []
        covered: set[str] = set()
        for root in roots:
            _flatten(root, level=1, selected=selected, covered=covered, units=units)

        parts: list[PlannedPart] = []
        for index, packed in enumerate(pack_units(units)):
            tokens = sum(unit.tokens for unit in packed)
            title = ", ".join(unit.title for unit in packed)
            topic_id_groups = tuple(unit.topic_id for unit in packed)
            parts.append(PlannedPart(index=index, title=title, tokens=tokens, topic_ids=topic_id_groups))
        return TopicPlan(parts=tuple(parts))


def _all_topic_ids(topic_tree: dict[str, Any]) -> frozenset[str]:
    ids: set[str] = set()

    def walk(node: dict[str, Any]) -> None:
        ids.add(str(node["id"]))
        for child in node.get("children", []):
            walk(child)

    for root in topic_tree.get("topics", []):
        walk(root)
    return frozenset(ids)


def _annotate_tokens(node: dict[str, Any], tokens_by_topic: dict[str, int]) -> None:
    """Fill ``node["tokens"]`` with the caller's per-topic subtree sum.

    The sums are already computed over whole subtrees by the caller
    (a part counts once per subtree), so no child recursion is needed.
    """
    node["tokens"] = tokens_by_topic.get(str(node["id"]), 0)
    for child in node.get("children", []):
        _annotate_tokens(child, tokens_by_topic)


__all__ = [
    "MAX_TOKENS",
    "MIN_FILL",
    "TAIL_GLUE",
    "TARGET_TOKENS",
    "PlannedPart",
    "TopicPlan",
    "TopicTreePlanner",
    "pack_units",
]
