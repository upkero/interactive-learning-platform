"""Source-preserving Markdown ranges shared by ingestion, tree building and segmentation."""

import re
from dataclasses import dataclass

from markdown_it import MarkdownIt

_MARKDOWN = MarkdownIt("default").enable("table")
_IMAGE = re.compile(r"!\[([^]\n]*)\]\(([^)\s]+)(?:\s+[^)]*)?\)")
_MARKER = re.compile(r'::image\{id="(img_\d+)"\}')
_HEADING = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.+?)[ \t]*$", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class Heading:
    start: int
    level: int
    title: str


@dataclass(frozen=True, slots=True)
class Image:
    start: int
    end: int
    caption: str
    source: str


@dataclass(frozen=True, slots=True)
class MarkdownStructure:
    headings: tuple[Heading, ...]
    images: tuple[Image, ...]
    blocks: tuple[tuple[int, int], ...]
    markers: tuple[tuple[int, str], ...] = ()


def inline_code_spans(text: str) -> list[tuple[int, int]]:
    """Backtick runs delimit inline code; unmatched runs remain ordinary text."""
    spans: list[tuple[int, int]] = []
    index = 0
    while index < len(text):
        if text[index] != "`":
            index += 1
            continue
        end = index
        while end < len(text) and text[end] == "`":
            end += 1
        run = text[index:end]
        closing = re.search(rf"(?<!`)`{{{len(run)}}}(?!`)", text[end:])
        if closing is None:
            index = end
            continue
        stop = end + closing.end()
        spans.append((index, stop))
        index = stop
    return spans


def parse_markdown(markdown: str) -> MarkdownStructure:
    lines = markdown.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    headings: list[Heading] = []
    images: dict[tuple[int, int], Image] = {}
    markers: dict[int, str] = {}
    ranges: list[tuple[int, int]] = []
    for token in _MARKDOWN.parse(markdown):
        if token.map is None:
            continue
        first, last = token.map
        if token.level == 0 and token.type != "inline" and token.nesting != -1:
            ranges.append((offsets[first], offsets[last]))
        if token.type == "heading_open" and token.tag in {"h1", "h2", "h3"}:
            match = _HEADING.match(lines[first])
            if match:
                title = re.sub(r"[ \t]+#+[ \t]*$", "", match.group(2)).strip()
                headings.append(Heading(offsets[first], int(token.tag[1]), title))
            elif last - first == 2:
                headings.append(Heading(offsets[first], int(token.tag[1]), lines[first].strip()))
        if token.type != "inline":
            continue
        # Inline token.map points at source lines; do not inspect fenced/code
        # blocks or HTML. A code span is masked with its exact source range.
        source = markdown[offsets[first] : offsets[last]]
        spans = inline_code_spans(source)
        for match in _IMAGE.finditer(source):
            if any(a <= match.start() < b for a, b in spans):
                continue
            start, end = offsets[first] + match.start(), offsets[first] + match.end()
            images[(start, end)] = Image(start, end, match.group(1), match.group(2))
        for match in _MARKER.finditer(source):
            if not any(a <= match.start() < b for a, b in spans):
                markers[offsets[first] + match.start()] = match.group(1)
    # Block ranges are line-aligned. Preserve all whitespace between adjacent
    # blocks by slicing the original string at their starting offsets.
    starts = sorted({start for start, _ in ranges if start < len(markdown)})
    if not starts or starts[0] != 0:
        starts.insert(0, 0)
    blocks = tuple((start, end) for start, end in zip(starts, [*starts[1:], len(markdown)], strict=True))
    return MarkdownStructure(tuple(headings), tuple(images.values()), blocks, tuple(markers.items()))
