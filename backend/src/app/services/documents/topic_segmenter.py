"""Bounded model windows and lossless topic boundaries at Markdown blocks."""

import re

from pydantic import BaseModel

from src.app.contracts.llm.llm_message import LLMMessage
from src.app.contracts.llm.llm_request import LLMRequest
from src.app.contracts.llm.system_block import SystemBlock
from src.app.ingest.markdown_syntax import MarkdownStructure, parse_markdown
from src.app.ingest.tokens import TokenCounter
from src.app.ingest.topic_tree import build_topic_tree, heading_level
from src.app.interfaces.llm.llm_client import LLMClient
from src.app.llm.structured import call_structured
from src.app.services.documents.prompts import TOPICS_SYSTEM

_WORD_BOUNDARY = re.compile(r"(?<=\S)[ \t]+(?=[^\W\d_])")


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

    def _blocks(self, markdown: str, structure: MarkdownStructure) -> list[tuple[int, int]]:
        blocks: list[tuple[int, int]] = []
        split_at = min(self._max_tokens // 2, 10000)
        for index, block in enumerate(structure.blocks):
            start = block.start if index else 0
            end = structure.blocks[index + 1].start if index + 1 < len(structure.blocks) else len(markdown)
            if not block.plain_text or self._counter.count(markdown[start:end]) <= split_at:
                blocks.append((start, end))
                continue
            cursor = start
            while cursor < end:
                if self._counter.count(markdown[cursor:end]) <= split_at:
                    blocks.append((cursor, end))
                    break
                # Start new paragraphs at letters so existing punctuation
                # cannot become a block marker after inserting a heading.
                whitespace = [match.end() for match in _WORD_BOUNDARY.finditer(markdown, cursor, block.end)]
                low, high = 0, len(whitespace)
                while low < high:
                    middle = (low + high) // 2
                    if self._counter.count(markdown[cursor : whitespace[middle]]) <= split_at:
                        low = middle + 1
                    else:
                        high = middle
                if low == 0:
                    raise ValueError("Cannot safely split a long Markdown block")
                cut = whitespace[low - 1]
                blocks.append((cursor, cut))
                cursor = cut
        return blocks

    async def segment(self, markdown: str) -> str:
        structure = parse_markdown(markdown)
        blocks = self._blocks(markdown, structure)
        if not blocks or not markdown.strip():
            return markdown
        valid: dict[int, str] = {}
        start = 0
        while start < len(blocks):
            end = start
            numbered = ""
            while end < len(blocks):
                candidate = numbered + f"[p{end + 1}] {markdown[slice(*blocks[end])]}"
                content = f"<document>\n{candidate}\n</document>"
                if self._counter.count(content) > 20000:
                    break
                numbered = candidate
                end += 1
            if end == start:
                raise ValueError("A Markdown block exceeds the model window")
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
            chunk = markdown[blocks[beginning - 1][0] : blocks[index][1]]
            if self._counter.count(f"{'#' * level} Topic\n\n{chunk}") > self._max_tokens:
                boundaries[index + 1] = f"Тема {index + 1}"
        parts: list[str] = []
        last = 0
        for number, title in sorted(boundaries.items()):
            pos = blocks[number - 1][0]
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
