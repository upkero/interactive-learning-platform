"""Prompt assembler for the template's plain-complete path.

Note (Grasp 2.1): there is no system role in LLMMessage — shared context
should be passed as SystemBlock to complete_structured instead.
"""

from collections.abc import Iterable

from src.app.contracts.llm.llm_message import LLMMessage, LLMRole


class PromptBuilder:
    def __init__(self) -> None:
        self._messages: list[LLMMessage] = []

    def add(self, *, role: LLMRole, content: str) -> "PromptBuilder":
        self._messages.append(LLMMessage(role=role, content=content))
        return self

    def user(self, content: str) -> "PromptBuilder":
        return self.add(role="user", content=content)

    def assistant(self, content: str) -> "PromptBuilder":
        return self.add(role="assistant", content=content)

    def extend(self, messages: Iterable[LLMMessage]) -> "PromptBuilder":
        self._messages.extend(messages)
        return self

    def build(self) -> list[LLMMessage]:
        return list(self._messages)
