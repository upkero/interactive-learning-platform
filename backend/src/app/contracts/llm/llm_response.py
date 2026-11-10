"""Plain completion response of an LLM provider."""

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LLMResponse:
    content: str
    model: str | None = None
    finish_reason: str | None = None
    # Token counters normalized to the TokenUsage field names
    # (input_tokens / output_tokens / cache_read_input_tokens /
    # cache_creation_input_tokens), regardless of the provider naming.
    usage: Mapping[str, int] | None = None
    metadata: Mapping[str, object] | None = None
