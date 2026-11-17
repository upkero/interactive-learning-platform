"""Plain completion response of an LLM provider."""

from collections.abc import Mapping
from dataclasses import dataclass

from src.app.contracts.llm.token_usage import TokenUsage


@dataclass(frozen=True, slots=True)
class LLMResponse:
    content: str
    model: str | None = None
    finish_reason: str | None = None
    usage: TokenUsage | None = None
    metadata: Mapping[str, object] | None = None
