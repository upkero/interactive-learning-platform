"""Deterministic, model-free packing of parsed topics into generation parts."""

import re
from bisect import bisect_left
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from itertools import pairwise

from src.app.contracts.documents import TopicNode
from src.app.contracts.documents.part_plan import PartPlan
from src.app.ingest.markdown_syntax import parse_markdown, protected_markdown_blocks
from src.app.ingest.tokens import TokenCounting

_MARKDOWN_BLOCK = re.compile(r"`{3,}|~{3,}|::image|\||^(?: {4}|\t)\S", re.MULTILINE)
_BLANK_LINES = re.compile(r"\n(?:[ \t]*\r?\n)+")
_HEADING_AND_GAP = re.compile(
    r"(?:[ \t]*#{1,6}(?:[ \t]+[^\n]*|[ \t]*)|[^\n]+\n[ \t]*(?:=+|-+)[ \t]*\r?)"
    r"(?:\n|\Z)(?:[ \t]*\r?\n)*"
)
_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")


@dataclass(frozen=True, slots=True)
class SplitLimits:
    target: int
    maximum: int

    def __post_init__(self) -> None:
        if not 0 < self.target <= self.maximum:
            raise ValueError("Expected 0 < split target <= maximum.")

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
    leading_topics: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class _Span:
    start: int
    end: int
    tokens: int


@dataclass(frozen=True, slots=True)
class _Paragraph:
    start: int
    end: int
    protected: tuple[tuple[int, int], ...]


def _tokens(units: list[Unit]) -> int:
    return sum(unit.tokens for unit in units)


def pack_units(
    units: list[Unit], limits: SplitLimits, *, measure: Callable[[list[Unit]], int] = _tokens
) -> list[list[Unit]]:
    parts: list[list[Unit]] = []
    current: list[Unit] = []
    size = 0
    for unit in units:
        if unit.tokens > limits.maximum:
            raise ValueError(f"Unit {unit.topic_id} exceeds maximum; split it first.")
        if current and _should_close(current, size, unit, limits):
            parts.extend(_bounded_part(current, limits.maximum, measure))
            current, size = [], 0
        current.append(unit)
        size += unit.tokens
    if current:
        parts.extend(_bounded_part(current, limits.maximum, measure))
    if len(parts) > 1 and measure(parts[-1]) < limits.tail:
        joined = parts[-2] + parts[-1]
        if measure(joined) <= limits.maximum:
            parts[-2:] = [joined]
    return parts


def _bounded_part(units: list[Unit], maximum: int, measure: Callable[[list[Unit]], int]) -> list[list[Unit]]:
    parts: list[list[Unit]] = []
    while units and measure(units) > maximum:
        # Each individual unit has already been measured. Check prefixes
        # only if the assembled Markdown pushes a proposed part over M.
        low, high = 1, len(units)
        while low + 1 < high:
            middle = (low + high) // 2
            if measure(units[:middle]) <= maximum:
                low = middle
            else:
                high = middle
        parts.append(units[:low])
        units = units[low:]
    if units:
        parts.append(units)
    return parts


def _should_close(current: list[Unit], size: int, unit: Unit, limits: SplitLimits) -> bool:
    new_size = size + unit.tokens
    if new_size > limits.maximum:
        return True
    if unit.chapter_id != current[-1].chapter_id and size >= limits.min_fill:
        return True
    if new_size <= limits.target:
        return False
    return size >= limits.min_fill


def _part_markdown(units: list[Unit], markdown: str) -> str:
    sections: list[str] = []
    first, end = units[0].start, units[0].end
    for unit in units[1:]:
        if unit.start != end:
            sections.append(markdown[first:end])
            first = unit.start
        end = unit.end
    sections.append(markdown[first:end])
    if len(sections) == 1:
        return sections[0]
    return "\n\n".join(section.strip("\r\n") for section in sections)


def to_plans(parts: list[list[Unit]], markdown: str, measure: Callable[[list[Unit]], int]) -> list[PartPlan]:
    result: list[PartPlan] = []
    for index, units in enumerate(parts):
        topics = dict.fromkeys(
            topic_id for unit in units for topic_id, _ in (*unit.leading_topics, (unit.topic_id, unit.title))
        )
        first = units[0].leading_topics[0][1] if units[0].leading_topics else units[0].title
        last = units[-1].title
        text = _part_markdown(units, markdown)
        result.append(
            PartPlan(
                index=index,
                title=first if first == last else f"{first} — {last}",
                topic_ids=tuple(topics),
                spans=tuple((unit.start, unit.end) for unit in units),
                tokens=measure(units),
                markdown=text,
            )
        )
    return result


def collect_units(
    roots: Sequence[TopicNode], selected: set[str], markdown: str, counter: TokenCounting, limits: SplitLimits
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
    counter: TokenCounting,
    limits: SplitLimits,
    out: list[Unit],
    *,
    chosen: bool,
    prefix_start: int | None = None,
    leading_topics: tuple[tuple[str, str], ...] = (),
) -> None:
    chosen = chosen or node.id in selected
    if not chosen:
        for child in node.children:
            _walk(child, chapter_id, selected, markdown, counter, limits, out, chosen=False)
        return

    start = node.start if prefix_start is None else prefix_start
    if node.total_tokens <= limits.maximum:
        tokens = counter.count(markdown[start : node.end])
        if tokens <= limits.maximum:
            out.append(Unit(node.id, chapter_id, node.title, start, node.end, tokens, leading_topics))
            return

    own_end = node.children[0].start if node.children else node.end
    if node.children and counter.count(markdown[start:own_end]) < limits.min_fill:
        # Carry a short chapter introduction into the first descendant, so
        # packing can never leave it behind at the end of a previous part.
        first, *rest = node.children
        _walk(
            first,
            chapter_id,
            selected,
            markdown,
            counter,
            limits,
            out,
            chosen=True,
            prefix_start=start,
            leading_topics=(*leading_topics, (node.id, node.title)),
        )
        for child in rest:
            _walk(child, chapter_id, selected, markdown, counter, limits, out, chosen=True)
        return
    for span in _paragraph_units(markdown, start, own_end, counter, limits):
        out.append(Unit(node.id, chapter_id, node.title, span.start, span.end, span.tokens, leading_topics))
        leading_topics = ()
    for child in node.children:
        _walk(child, chapter_id, selected, markdown, counter, limits, out, chosen=True)


def split_by_paragraphs(
    markdown: str, start: int, end: int, counter: TokenCounting, limits: SplitLimits
) -> list[tuple[int, int]]:
    return [(span.start, span.end) for span in _paragraph_units(markdown, start, end, counter, limits)]


def _paragraph_units(markdown: str, start: int, end: int, counter: TokenCounting, limits: SplitLimits) -> list[_Span]:
    result: list[_Span] = []
    current: list[_Span] = []
    size = 0

    def close() -> None:
        if len(current) == 1:
            result.extend(current)
        elif current:
            first, last = current[0].start, current[-1].end
            actual = counter.count(markdown[first:last])
            if actual <= limits.target:
                result.append(_Span(first, last, actual))
            else:
                # Subword tokenization can grow at a join. Each component is
                # already known to fit M, including an indivisible block > T.
                result.extend(current)
        current.clear()

    for paragraph in _paragraph_spans(markdown, start, end, counter, limits.maximum):
        paragraph_start, paragraph_end = paragraph.start, paragraph.end
        tokens = counter.count(markdown[paragraph_start:paragraph_end])
        spans = (
            [_Span(paragraph_start, paragraph_end, tokens)]
            if tokens <= limits.maximum
            else _split_large(
                markdown,
                paragraph_start,
                paragraph_end,
                counter,
                limits.maximum,
                tuple(
                    (left, right)
                    for left, right in paragraph.protected
                    if counter.count(markdown[left:right]) <= limits.maximum
                ),
            )
        )
        for span in spans:
            if current and size + span.tokens > limits.target:
                close()
                size = 0
            current.append(span)
            size += span.tokens
    close()
    return result


def _heading_end(text: str) -> int:
    end = 0
    while match := _HEADING_AND_GAP.match(text, end):
        end = match.end()
    return end


def _paragraph_spans(markdown: str, start: int, end: int, counter: TokenCounting, maximum: int) -> list[_Paragraph]:
    text = markdown[start:end]
    boundaries = {match.end() for match in _BLANK_LINES.finditer(text)}
    markers: set[int] = set()
    atomic_blocks: dict[int, int] = {}
    if _MARKDOWN_BLOCK.search(text):
        for block in protected_markdown_blocks(text):
            atomic_blocks[block.start] = block.end
            boundaries.difference_update(
                boundary.end() for boundary in _BLANK_LINES.finditer(text, block.start, block.end)
            )
            boundaries.update((block.start, block.end))
        if "::image" in text:
            markers = {offset for offset, _ in parse_markdown(text).markers}
    # Consecutive headings belong to the first body paragraph. An image
    # paragraph belongs to the preceding content even across blank lines.
    heading_end = _heading_end(text)
    spans: list[tuple[int, int]] = []
    left = 0
    for right in sorted({*boundaries, len(text)}):
        if left == right:
            continue
        if (
            right <= heading_end
            and right != len(text)
            and (right not in atomic_blocks or counter.count(text[: atomic_blocks[right]]) <= maximum)
        ):
            continue
        if spans and (left in markers or not text[left:right].strip()):
            spans[-1] = (spans[-1][0], start + right)
        else:
            spans.append((start + left, start + right))
        left = right
    blocks = sorted(atomic_blocks.items())
    block_starts = [block_start for block_start, _ in blocks]
    paragraphs: list[_Paragraph] = []
    for left, right in spans:
        first = bisect_left(block_starts, left - start)
        last = bisect_left(block_starts, right - start)
        protected = tuple(
            (start + block_start, start + block_end)
            for block_start, block_end in blocks[first:last]
            if start + block_end <= right
        )
        paragraphs.append(_Paragraph(left, right, protected))
    return paragraphs


def _split_large(
    markdown: str,
    start: int,
    end: int,
    counter: TokenCounting,
    maximum: int,
    blocks: tuple[tuple[int, int], ...],
) -> list[_Span]:
    text = markdown[start:end]
    protected = [(left - start, right - start) for left, right in blocks]
    heading_end = _heading_end(text)
    if 0 < heading_end < len(text) and counter.count(text[: heading_end + 1]) <= maximum:
        protected.append((0, heading_end + 1))
    if "::image" in text:
        for offset, _ in parse_markdown(text).markers:
            previous = offset - 1
            while previous >= 0 and text[previous].isspace():
                previous -= 1
            end_of_marker = text.find("\n", offset)
            marker_end = len(text) if end_of_marker == -1 else end_of_marker
            marker_start = max(0, previous)
            if any(left <= marker_start < right for left, right in protected):
                marker_start = offset
            protected.append((marker_start, marker_end))
    boundaries = [
        0,
        *(point for block in protected[: len(blocks)] for point in block if 0 < point < len(text)),
        *(
            match.end()
            for match in _SENTENCE_END.finditer(text)
            if match.end() < len(text) and all(not left < match.end() < right for left, right in protected)
        ),
        len(text),
    ]
    spans: list[_Span] = []
    for left, right in pairwise(sorted(set(boundaries))):
        sentence = text[left:right]
        tokens = counter.count(sentence)
        if tokens <= maximum:
            spans.append(_Span(start + left, start + right, tokens))
            continue
        local = tuple((a - left, b - left) for a, b in protected if a < right and b > left)
        for a, b in counter.chunk_spans(sentence, maximum, local):
            spans.append(_Span(start + left + a, start + left + b, counter.count(sentence[a:b])))
    return spans


def split_document(
    tree: Sequence[TopicNode], selected: set[str], markdown: str, counter: TokenCounting, limits: SplitLimits
) -> list[PartPlan]:
    if not selected:
        return []
    units = collect_units(tree, selected, markdown, counter, limits)
    measured: dict[tuple[tuple[int, int], ...], int] = {}

    def measure(part: list[Unit]) -> int:
        if len(part) == 1:
            return part[0].tokens
        spans = tuple((unit.start, unit.end) for unit in part)
        if spans not in measured:
            measured[spans] = counter.count(_part_markdown(part, markdown))
        return measured[spans]

    parts = pack_units(units, limits, measure=measure)
    return to_plans(parts, markdown, measure)
