"""LLM request carrying an explicit purpose.

``purpose`` is a short name of the resolver step; it drives the
``llm_complete_*`` metrics and the decision log. Full value list — LLMPurpose.
"""

from dataclasses import dataclass, field
from typing import Literal

from src.app.contracts.llm.llm_message import LLMMessage
from src.app.contracts.llm.system_block import SystemBlock

LLMPurpose = Literal[
    "main_pass",
    "rerank",
    "config_build",
    "config_check",
    "describe",
    "codegen",
    "judge",
    "quiz_gen",
    "quiz_verify",
    "vision",
    "topics",
    "merge_confirm",
]


@dataclass(frozen=True, slots=True)
class LLMRequest:
    purpose: LLMPurpose
    messages: tuple[LLMMessage, ...]
    system: tuple[SystemBlock, ...] = ()
    max_tokens: int = 4096
    temperature: float | None = 0.0
    # document_id, part_id — для логов и журнала решений
    metadata: dict[str, str] = field(default_factory=dict)
