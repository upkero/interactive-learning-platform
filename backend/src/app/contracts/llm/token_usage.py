"""Token usage of a completed LLM call.

Shared by plain completions (``LLMResponse.usage``) and structured ones
(``StructuredResponse.usage``); the four cache fields mirror the Anthropic
usage contract, the OpenAI one reports only cache reads.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TokenUsage:
    input_tokens: int
    output_tokens: int
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0
