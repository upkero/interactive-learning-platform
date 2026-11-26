"""Source ranges and token kinds shared by the Markdown ingest pipeline."""

import re
from bisect import bisect_right
from collections.abc import Callable
from dataclasses import dataclass

from markdown_it import MarkdownIt
from markdown_it.renderer import RendererHTML
from markdown_it.rules_inline import StateInline, backtick, html_inline, image
from markdown_it.token import Token

_MARKER = re.compile(r'::image\{id="(img_\d+)"\}')
_TABLE_ESCAPE = re.compile(r"\\(?=\|)")


def _with_source_range(rule: Callable[[StateInline, bool], bool]) -> Callable[[StateInline, bool], bool]:
    def capture(state: StateInline, silent: bool) -> bool:
        start, token_count = state.pos, len(state.tokens)
        matched = rule(state, silent)
        if matched and not silent and len(state.tokens) > token_count:
            state.tokens[-1].meta["source_range"] = (start, state.pos)
        return matched

    return capture


class _IngestMarkdown(MarkdownIt):
    def validateLink(self, url: str) -> bool:
        return super().validateLink(url) or url.lower().startswith("data:image/jpg;")


_MARKDOWN = _IngestMarkdown("default").enable("table")
_MARKDOWN.inline.ruler.at("image", _with_source_range(image))
_MARKDOWN.inline.ruler.at("backticks", _with_source_range(backtick))
_MARKDOWN.inline.ruler.at("html_inline", _with_source_range(html_inline))
_RENDERER = RendererHTML()


@dataclass(frozen=True, slots=True)
class Heading:
    start: int
    end: int
    level: int
    title: str
    markup: str


@dataclass(frozen=True, slots=True)
class Block:
    start: int
    end: int
    kind: str
    plain_text: bool = False


@dataclass(frozen=True, slots=True)
class Image:
    start: int
    end: int
    caption: str
    source: str
    block: Block


@dataclass(frozen=True, slots=True)
class MarkdownStructure:
    headings: tuple[Heading, ...]
    images: tuple[Image, ...]
    blocks: tuple[Block, ...]
    markers: tuple[tuple[int, str], ...]
    protected_blocks: tuple[Block, ...] = ()


def _find_images(
    inline: Token, lines: list[str], offsets: list[int], block: Block, row_columns: dict[int, int], *, table: bool
) -> list[Image]:
    assert inline.map is not None
    tokens = [child for child in inline.children or () if child.type == "image"]
    first = inline.map[0]
    if not tokens and not table:
        return []
    # Inline content strips container prefixes and trims cell edges. Match
    # the token's source lines back to the original lines in reading order.
    ranges: list[tuple[int, int, int, tuple[int, ...]]] = []
    cursor = 0
    for line, content in enumerate(inline.content.split("\n"), first):
        raw = lines[line]
        escapes = tuple(match.start() - i for i, match in enumerate(_TABLE_ESCAPE.finditer(raw))) if table else ()
        source = _TABLE_ESCAPE.sub("", raw) if escapes else raw
        column = source.find(content, row_columns.get(line, 0) if table else 0)
        if column < 0:
            return []
        if table:
            row_columns[line] = column + len(content)
        ranges.append((cursor, cursor + len(content), offsets[line] + column, escapes))
        cursor += len(content) + 1

    def source_position(position: int) -> int:
        for line, (start, end, base, escapes) in enumerate(ranges, first):
            if start <= position <= end:
                mapped = base + position - start
                return mapped + bisect_right(escapes, mapped - offsets[line])
        raise ValueError("Image position outside its Markdown inline token")

    return [
        Image(
            source_position(child.meta["source_range"][0]),
            source_position(child.meta["source_range"][1] - 1) + 1,
            _RENDERER.renderInlineAsText(child.children or [], _MARKDOWN.options, {}),
            str(child.attrGet("src")),
            block,
        )
        for child in tokens
    ]


def parse_markdown(markdown: str, *, extract_images: bool = False) -> MarkdownStructure:
    lines: list[str] = []
    offsets = [0]
    for ending in re.finditer(r"\r\n?|\n", markdown):
        lines.append(markdown[offsets[-1] : ending.start()])
        offsets.append(ending.end())
    if offsets[-1] < len(markdown):
        lines.append(markdown[offsets[-1] :])
        offsets.append(len(markdown))
    tokens = _MARKDOWN.parse(markdown)
    headings: list[Heading] = []
    images: list[Image] = []
    markers: list[tuple[int, str]] = []
    blocks: list[Block] = []
    protected_blocks: list[Block] = []
    row_columns: dict[int, int] = {}
    for index, token in enumerate(tokens):
        if token.map is None:
            continue
        first, last = token.map
        if token.type in {"fence", "code_block", "table_open"}:
            protected_blocks.append(Block(offsets[first], offsets[last], token.type))
        if token.level == 0 and token.type != "inline" and token.nesting != -1:
            plain = token.type == "paragraph_open" and all(
                child.type in {"text", "softbreak"} for child in tokens[index + 1].children or ()
            )
            blocks.append(Block(offsets[first], offsets[last], token.type, plain))
            if token.type == "heading_open" and token.tag in {"h1", "h2", "h3"}:
                headings.append(
                    Heading(offsets[first], offsets[last], int(token.tag[1]), tokens[index + 1].content, token.markup)
                )
        if token.type != "inline":
            continue
        previous = tokens[index - 1]
        if previous.type == "paragraph_open" and previous.level == 0 and "::image" in token.content:
            protected = [child.meta["source_range"] for child in token.children or () if "source_range" in child.meta]
            inline_offset = 0
            for line, content in enumerate(token.content.split("\n"), first):
                if (
                    (match := _MARKER.fullmatch(lines[line]))
                    and content == lines[line]
                    and all(not start <= inline_offset < end for start, end in protected)
                ):
                    markers.append((offsets[line], match.group(1)))
                inline_offset += len(content) + 1
        if extract_images:
            images.extend(
                _find_images(token, lines, offsets, blocks[-1], row_columns, table=previous.tag in {"td", "th"})
            )
    return MarkdownStructure(tuple(headings), tuple(images), tuple(blocks), tuple(markers), tuple(protected_blocks))


def escape_image_markers(markdown: str, structure: MarkdownStructure) -> str:
    """Preserve literal user text without treating it as extracted image metadata."""
    for start, _ in reversed(structure.markers):
        markdown = markdown[:start] + "\\" + markdown[start:]
    return markdown
