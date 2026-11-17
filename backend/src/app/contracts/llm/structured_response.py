"""Structured LLM call result: a validated pydantic object plus token usage."""

from dataclasses import dataclass

from src.app.contracts.llm.token_usage import TokenUsage


@dataclass(frozen=True, slots=True)
class StructuredResponse[T]:
    value: T
    usage: TokenUsage | None = None
