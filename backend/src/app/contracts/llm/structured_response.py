"""Structured LLM call result: a validated pydantic object plus token usage."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TokenUsage:
    input_tokens: int
    output_tokens: int
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0


@dataclass(frozen=True, slots=True)
class StructuredResponse[T]:
    value: T
    usage: TokenUsage | None = None
