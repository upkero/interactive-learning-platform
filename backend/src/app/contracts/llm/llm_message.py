"""Chat message of the resolver.

No system role in Grasp: shared context is passed as separate
:class:`~src.app.contracts.llm.system_block.SystemBlock` entries (needed for
prompt caching and provider-agnostic behaviour).
"""

from dataclasses import dataclass
from typing import Literal

from src.app.contracts.llm.image_part import ImagePart
from src.app.contracts.llm.text_part import TextPart

LLMRole = Literal["user", "assistant"]

LLMContent = str | tuple[TextPart | ImagePart, ...]


@dataclass(frozen=True, slots=True)
class LLMMessage:
    role: LLMRole
    content: LLMContent
