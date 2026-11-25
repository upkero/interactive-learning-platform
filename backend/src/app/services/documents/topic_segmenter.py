import re

from pydantic import BaseModel

from src.app.contracts.llm.llm_message import LLMMessage
from src.app.contracts.llm.llm_request import LLMRequest
from src.app.contracts.llm.system_block import SystemBlock
from src.app.ingest.tokens import TokenCounter
from src.app.interfaces.llm.llm_client import LLMClient
from src.app.llm.structured import call_structured
from src.app.services.documents.prompts import TOPICS_SYSTEM


class Section(BaseModel):
    title: str
    first_paragraph: int


class Sections(BaseModel):
    sections: list[Section]


class TopicSegmenter:
    """Insert model-suggested headings into bounded overlapping text windows."""

    def __init__(self, llm: LLMClient, *, counter: TokenCounter, max_tokens: int = 22000) -> None:
        self._llm = llm
        self._counter = counter
        self._max_tokens = max_tokens

    async def segment(self, markdown: str) -> str:
        paragraphs = [part for part in re.split(r"\n\s*\n", markdown) if part.strip()]
        if not paragraphs:
            return markdown
        valid: list[tuple[int, str]] = []
        start = 0
        while start < len(paragraphs):
            end = start
            tokens = 0
            while end < len(paragraphs):
                count = self._counter.count(paragraphs[end])
                if end > start and tokens + count > 20000:
                    break
                tokens += count
                end += 1
            numbered = "\n\n".join(f"[p{index + 1}] {paragraphs[index]}" for index in range(start, end))
            request = LLMRequest(
                purpose="topics",
                system=(SystemBlock(TOPICS_SYSTEM, cache=True),),
                messages=(LLMMessage(role="user", content=f"<document>\n{numbered}\n</document>"),),
                max_tokens=2048,
            )
            result = await call_structured(self._llm, request, Sections)
            positions = [(section.first_paragraph, section.title.strip()) for section in result.sections]
            previous = start
            for number, title in positions:
                if not title or number <= previous or number > end:
                    raise ValueError("Invalid or non-monotonic topic boundaries")
                previous = number
                if not valid or number > valid[-1][0]:
                    valid.append((number, title))
            if end == len(paragraphs):
                break
            start = max(start + 1, end - 1)
        if not valid or valid[0][0] != 1:
            valid.insert(0, (1, "Вступление"))
        for index, (number, title) in enumerate(valid):
            stop = valid[index + 1][0] - 1 if index + 1 < len(valid) else len(paragraphs)
            section = f"## {title}\n\n" + "\n\n".join(paragraphs[number - 1 : stop]) + "\n"
            if self._counter.count(section) > self._max_tokens:
                raise ValueError("Topic exceeds the configured token limit")
        output: list[str] = []
        by_position = dict(valid)
        for index, paragraph in enumerate(paragraphs, 1):
            if index in by_position:
                output.append(f"## {by_position[index]}")
            output.append(paragraph)
        return "\n\n".join(output) + "\n"
