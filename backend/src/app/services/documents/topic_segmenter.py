import re
from typing import Any

from pydantic import BaseModel

from src.app.contracts.llm.llm_message import LLMMessage
from src.app.contracts.llm.llm_request import LLMRequest
from src.app.contracts.llm.system_block import SystemBlock
from src.app.ingest.tokens import TokenCounter
from src.app.llm.structured import call_structured
from src.app.services.documents.prompts import TOPICS_SYSTEM


class Section(BaseModel):
    title: str
    first_paragraph: int


class Sections(BaseModel):
    sections: list[Section]


class TopicSegmenter:
    def __init__(self, llm: Any, *, counter: TokenCounter, max_tokens: int = 12000) -> None:
        self._llm, self._counter, self._max_tokens = llm, counter, max_tokens

    async def segment(self, markdown: str) -> str:
        paragraphs = [part for part in re.split(r"\n\s*\n", markdown) if part.strip()]
        numbered = "\n\n".join(f"[p{index}] {paragraph}" for index, paragraph in enumerate(paragraphs, 1))
        request = LLMRequest(
            purpose="topics",
            system=(SystemBlock(TOPICS_SYSTEM, cache=True),),
            messages=(LLMMessage(role="user", content=f"<document>\n{numbered}\n</document>"),),
            max_tokens=2048,
        )
        result = await call_structured(self._llm, request, Sections)
        positions = sorted(
            (section.first_paragraph, section.title.strip()) for section in result.sections if section.title.strip()
        )
        valid = [(number, title) for number, title in positions if 1 <= number <= len(paragraphs)]
        if not valid or valid[0][0] != 1:
            valid.insert(0, (1, "Введение"))
        output: list[str] = []
        by_position = dict(valid)
        for index, paragraph in enumerate(paragraphs, 1):
            if index in by_position:
                output.append(f"## {by_position[index]}")
            output.append(paragraph)
        return "\n\n".join(output) + "\n"
