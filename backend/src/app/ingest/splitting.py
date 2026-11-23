"""Deterministic, model-free packing of parsed topics into generation parts."""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise

from src.app.contracts.documents import TopicNode
from src.app.contracts.documents.part_plan import PartPlan
from src.app.ingest.tokens import TokenCounter


@dataclass(frozen=True, slots=True)
class SplitLimits:
    target: int = 15_000
    maximum: int = 22_000

    @property
    def min_fill(self) -> int:
        return self.target // 2

    @property
    def tail(self) -> int:
        return self.target // 3


@dataclass(frozen=True, slots=True)
class Unit:
    topic_id: str
    chapter_id: str
    title: str
    start: int
    end: int
    tokens: int


def pack_units(units: list[Unit], limits: SplitLimits) -> list[list[Unit]]:
    parts: list[list[Unit]] = []
    current: list[Unit] = []
    size = 0
    for unit in units:
        if unit.tokens > limits.maximum:
            raise ValueError(f"Unit {unit.topic_id} exceeds maximum; split it first.")
        if current and _should_close(current, size, unit, limits):
            parts.append(current)
            current, size = [], 0
        current.append(unit)
        size += unit.tokens
    if current:
        parts.append(current)
    return _glue_tail(parts, limits)


def _should_close(current: list[Unit], size: int, unit: Unit, limits: SplitLimits) -> bool:
    new_size = size + unit.tokens
    if new_size > limits.maximum:
        return True
    if unit.chapter_id != current[-1].chapter_id and size >= limits.min_fill:
        return True
    if new_size <= limits.target:
        return False
    return size >= limits.min_fill


def _glue_tail(parts: list[list[Unit]], limits: SplitLimits) -> list[list[Unit]]:
    if len(parts) < 2:
        return parts
    last, previous = _tokens(parts[-1]), _tokens(parts[-2])
    if last < limits.tail and previous + last <= limits.maximum:
        return [*parts[:-2], parts[-2] + parts[-1]]
    return parts


def _tokens(units: list[Unit]) -> int:
    return sum(unit.tokens for unit in units)


def to_plans(parts: list[list[Unit]], markdown: str) -> list[PartPlan]:
    result: list[PartPlan] = []
    for index, units in enumerate(parts):
        topic_ids = tuple(dict.fromkeys(unit.topic_id for unit in units))
        first, last = units[0].title, units[-1].title
        text = "\n\n".join(markdown[start:end].strip("\n") for start, end in ((u.start, u.end) for u in units))
        result.append(
            PartPlan(
                index,
                first if first == last else f"{first} — {last}",
                topic_ids,
                tuple((unit.start, unit.end) for unit in units),
                _tokens(units),
                text,
            )
        )
    return result


def collect_units(
    roots: Sequence[TopicNode], selected: set[str], markdown: str, counter: TokenCounter, limits: SplitLimits
) -> list[Unit]:
    units: list[Unit] = []
    for root in roots:
        _walk(root, root.id, selected, markdown, counter, limits, units, chosen=False)
    return units


def _walk(
    node: TopicNode,
    chapter_id: str,
    selected: set[str],
    markdown: str,
    counter: TokenCounter,
    limits: SplitLimits,
    out: list[Unit],
    *,
    chosen: bool,
) -> None:
    chosen = chosen or node.id in selected
    if not chosen:
        for child in node.children:
            _walk(child, chapter_id, selected, markdown, counter, limits, out, chosen=False)
        return
    unit = _unit(node, chapter_id, node.start, node.end, markdown, counter)
    if unit.tokens <= limits.maximum:
        out.append(unit)
        return
    own_end = node.children[0].start if node.children else node.end
    for start, end in split_by_paragraphs(markdown, node.start, own_end, counter, limits):
        out.append(_unit(node, chapter_id, start, end, markdown, counter))
    for child in node.children:
        _walk(child, chapter_id, selected, markdown, counter, limits, out, chosen=True)


def _unit(node: TopicNode, chapter_id: str, start: int, end: int, markdown: str, counter: TokenCounter) -> Unit:
    return Unit(node.id, chapter_id, node.title, start, end, counter.count(markdown[start:end]))


def split_by_paragraphs(
    markdown: str, start: int, end: int, counter: TokenCounter, limits: SplitLimits
) -> list[tuple[int, int]]:
    paragraphs = _paragraph_spans(markdown, start, end)
    result: list[tuple[int, int]] = []
    current_start: int | None = None
    current_end = start
    for paragraph_start, paragraph_end in paragraphs:
        paragraph_tokens = counter.count(markdown[paragraph_start:paragraph_end])
        spans = (
            [(paragraph_start, paragraph_end)]
            if paragraph_tokens <= limits.maximum
            else _split_large(markdown, paragraph_start, paragraph_end, counter, limits)
        )
        for span_start, span_end in spans:
            if current_start is not None and counter.count(markdown[current_start:span_end]) > limits.target:
                result.append((current_start, current_end))
                current_start = None
            if current_start is None:
                current_start = span_start
            current_end = span_end
    if current_start is not None:
        result.append((current_start, current_end))
    return result


def _paragraph_spans(markdown: str, start: int, end: int) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    cursor = start
    in_fence = False
    paragraph_start = start
    for line in re.finditer(r".*(?:\n|$)", markdown[start:end]):
        line_start = start + line.start()
        line_end = start + line.end()
        stripped = line.group().strip()
        if stripped.startswith(("```", "~~~")):
            in_fence = not in_fence
        if not in_fence and not stripped and line_start > paragraph_start:
            spans.append((paragraph_start, line_end))
            paragraph_start = line_end
        cursor = line_end
    if paragraph_start < min(cursor, end):
        spans.append((paragraph_start, min(cursor, end)))
    if not spans and start < end:
        spans.append((start, end))
    # Keep image directives with the preceding paragraph, even when the source
    # contains a blank line before the directive.
    merged: list[tuple[int, int]] = []
    for span_start, span_end in spans:
        if markdown[span_start:span_end].lstrip().startswith("::image") and merged:
            previous_start, _ = merged[-1]
            merged[-1] = (previous_start, span_end)
        else:
            merged.append((span_start, span_end))
    return merged


def _split_large(
    markdown: str, start: int, end: int, counter: TokenCounter, limits: SplitLimits
) -> list[tuple[int, int]]:
    boundaries = [start, *(start + match.end() for match in re.finditer(r"(?<=[.!?…])\s+", markdown[start:end])), end]
    spans: list[tuple[int, int]] = []
    for sentence_start, sentence_end in pairwise(boundaries):
        if sentence_start == sentence_end:
            continue
        while counter.count(markdown[sentence_start:sentence_end]) > limits.maximum:
            # Search character boundaries so UTF-8 code points remain intact.
            low, high = sentence_start, sentence_end
            while low + 1 < high:
                middle = (low + high) // 2
                encoded = counter.encode(markdown[sentence_start:middle])
                decoded = counter.decode(encoded)
                if counter.count(decoded) <= limits.maximum:
                    low = middle
                else:
                    high = middle
            if low == sentence_start:
                raise ValueError("Split limit cannot accommodate one Unicode character.")
            spans.append((sentence_start, low))
            sentence_start = low
        spans.append((sentence_start, sentence_end))
    return spans or [(start, end)]


def split_document(
    tree: Sequence[TopicNode], selected: set[str], markdown: str, counter: TokenCounter, limits: SplitLimits
) -> list[PartPlan]:
    if not selected:
        return []
    return to_plans(pack_units(collect_units(tree, selected, markdown, counter, limits), limits), markdown)
