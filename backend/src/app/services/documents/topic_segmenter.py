"""Bounded model windows and lossless topic boundaries at Markdown blocks."""

import re
from bisect import bisect_right
from collections.abc import Mapping
from itertools import accumulate, pairwise

from pydantic import BaseModel

from src.app.contracts.llm.llm_message import LLMMessage
from src.app.contracts.llm.llm_request import LLMRequest
from src.app.contracts.llm.system_block import SystemBlock
from src.app.ingest.markdown_syntax import Block, MarkdownStructure, parse_markdown
from src.app.ingest.tokens import TokenCounter
from src.app.ingest.topic_tree import build_topic_tree, heading_level
from src.app.interfaces.llm.llm_client import LLMClient
from src.app.llm.structured import call_structured
from src.app.services.documents.prompts import TOPICS_SYSTEM

_WORD_BOUNDARY = re.compile(r"(?<=\S)[ \t]+(?=[^\W\d_])")
_MODEL_WINDOW_TOKENS = 20000
# Allow two ordinary fragments plus their labels and image directives to overlap.
_PARAGRAPH_WINDOW_TOKENS = 9900


class Section(BaseModel):
    title: str
    first_paragraph: int


class Sections(BaseModel):
    sections: list[Section]


class TopicSegmenter:
    """Suggest headings without asking the model to rewrite document content."""

    def __init__(self, llm: LLMClient, *, counter: TokenCounter, max_tokens: int = 22000) -> None:
        self._llm = llm
        self._counter = counter
        self._max_tokens = max_tokens

    def _blocks(
        self, markdown: str, structure: MarkdownStructure, image_spans: Mapping[str, tuple[int, int]]
    ) -> list[str]:
        marker_refs = dict(structure.markers)
        grouped: list[tuple[Block, list[tuple[Block, str]]]] = []
        for block in structure.blocks:
            ref = marker_refs.get(block.start)
            if (
                grouped
                and ref is not None
                and markdown[block.start : block.end].rstrip("\r\n") == f'::image{{id="{ref}"}}'
            ):
                grouped[-1][1].append((block, ref))
            else:
                grouped.append((block, []))

        blocks: list[str] = []
        split_at = min(self._max_tokens // 2, _PARAGRAPH_WINDOW_TOKENS)
        for index, (block, markers) in enumerate(grouped):
            start = block.start if index else 0
            end = grouped[index + 1][0].start if index + 1 < len(grouped) else len(markdown)
            if not block.plain_text or self._counter.count(markdown[start : block.end]) <= split_at:
                blocks.append(markdown[start:end])
                continue
            anchors = {
                ref: (block.start + span[0], block.start + span[1])
                for _, ref in markers
                if (span := image_spans.get(ref)) is not None and 0 <= span[0] <= span[1] <= block.end - block.start
            }
            cuts = self._paragraph_cuts(markdown, start, block.end, split_at, anchors)
            if not cuts:
                blocks.append(markdown[start:end])
                continue
            fragments = [markdown[left:right] for left, right in pairwise((start, *cuts, block.end))]
            moved: list[list[str]] = [[] for _ in cuts]
            tail: list[str] = []
            cursor = block.end
            for marker, ref in markers:
                anchor = anchors.get(ref)
                fragment = bisect_right(cuts, anchor[0]) if anchor is not None else len(cuts)
                if fragment == len(cuts):
                    continue
                moved[fragment].append(markdown[marker.start : marker.end].rstrip("\r\n"))
                tail.append(markdown[cursor : marker.start])
                cursor = marker.end
                # Drop the empty separator following a relocated directive.
                if markdown.startswith("\r\n", cursor):
                    cursor += 2
                elif markdown[cursor : cursor + 1] in {"\r", "\n"}:
                    cursor += 1
            for index, refs in enumerate(moved):
                if refs:
                    fragments[index] += "\n\n" + "\n\n".join(refs) + "\n\n"
            fragments[-1] += "".join(tail) + markdown[cursor:end]
            blocks.extend(fragments)
        return blocks

    def _paragraph_cuts(
        self, markdown: str, start: int, end: int, split_at: int, anchors: Mapping[str, tuple[int, int]]
    ) -> list[int]:
        # Start at a word boundary without cutting the alt text it belongs to.
        whitespace = [
            match.end()
            for match in _WORD_BOUNDARY.finditer(markdown, start, end)
            if all(not left < match.end() < right for left, right in anchors.values())
        ]
        cuts: list[int] = []
        cursor = start
        while self._counter.count(markdown[cursor:end]) > split_at:
            first = bisect_right(whitespace, cursor)
            low, high = first, len(whitespace)
            while low < high:
                middle = (low + high) // 2
                if self._counter.count(markdown[cursor : whitespace[middle]]) <= split_at:
                    low = middle + 1
                else:
                    high = middle
            if low == first:
                raise ValueError("Cannot safely split a long Markdown block")
            cursor = whitespace[low - 1]
            cuts.append(cursor)
        return cuts

    async def segment(self, markdown: str, *, image_spans: Mapping[str, tuple[int, int]] | None = None) -> str:
        structure = parse_markdown(markdown)
        blocks = self._blocks(markdown, structure, image_spans or {})
        if not blocks or not markdown.strip():
            return markdown
        numbered_blocks = [f"[p{index}] {block}" for index, block in enumerate(blocks, 1)]
        if any(
            self._counter.count(f"<document>\n{block}\n</document>") > _MODEL_WINDOW_TOKENS for block in numbered_blocks
        ):
            raise ValueError("A Markdown block exceeds the model window")
        offsets = (0, *accumulate(map(len, blocks)))
        markdown = "".join(blocks)
        valid: dict[int, str] = {}
        start = 0
        while start < len(blocks):
            end = start
            numbered = ""
            while end < len(blocks):
                candidate = numbered + numbered_blocks[end]
                content = f"<document>\n{candidate}\n</document>"
                if self._counter.count(content) > _MODEL_WINDOW_TOKENS:
                    break
                numbered = candidate
                end += 1
            request = LLMRequest(
                purpose="topics",
                system=(SystemBlock(TOPICS_SYSTEM, cache=True),),
                messages=(LLMMessage(role="user", content=f"<document>\n{numbered}\n</document>"),),
                max_tokens=2048,
            )
            result = await call_structured(self._llm, request, Sections)
            previous = start
            for section in result.sections:
                number, title = section.first_paragraph, " ".join(section.title.split())
                if not title or number <= previous or number > end:
                    raise ValueError("Invalid or non-monotonic topic boundaries")
                previous = number
                valid.setdefault(number, title)
            if end == len(blocks):
                break
            start = max(start + 1, end - 1)

        existing = structure.headings
        level = existing[0].level if existing else 2
        if not existing:
            valid.setdefault(1, "Вступление")
        else:
            valid.pop(1, None)
        # Fill gaps that the model left too large. Validate the *actual tree*,
        # including inserted heading tokens, not only unadorned paragraphs.
        boundaries = dict(valid)
        for index in range(len(blocks)):
            if index == 0 or index + 1 in boundaries:
                continue
            beginning = max((pos for pos in boundaries if pos <= index), default=1)
            chunk = markdown[offsets[beginning - 1] : offsets[index + 1]]
            if self._counter.count(f"{'#' * level} Topic\n\n{chunk}") > self._max_tokens:
                boundaries[index + 1] = f"Тема {index + 1}"
        parts: list[str] = []
        last = 0
        for number, title in sorted(boundaries.items()):
            pos = offsets[number - 1]
            parts.append(markdown[last:pos])
            if pos and parts[-1] and not parts[-1].endswith("\n\n"):
                parts.append("\n\n")
            if heading_level(title, level) != level:
                title = f"Тема: {title}"
            parts.append(f"{'#' * level} {title}\n\n")
            last = pos
        parts.append(markdown[last:])
        output = "".join(parts)
        if not output.endswith("\n"):
            output += "\n"
        if any(node.total_tokens > self._max_tokens for node in build_topic_tree(output, self._counter)):
            raise ValueError("Topic exceeds the configured token limit")
        return output
