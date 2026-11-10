"""LLM access interface.

Services depend only on this interface. Importable provider SDKs are banned
outside llm/ (ruff banned-api); provider errors must not escape llm/ — they
are mapped to our exceptions from exceptions/llm.py.
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence

from pydantic import BaseModel

from src.app.contracts.llm.llm_message import LLMMessage
from src.app.contracts.llm.llm_request import LLMRequest
from src.app.contracts.llm.llm_response import LLMResponse
from src.app.contracts.llm.structured_response import StructuredResponse


class LLMClient(ABC):
    @property
    @abstractmethod
    def model_name(self) -> str: ...

    @property
    @abstractmethod
    def provider_name(self) -> str: ...

    @abstractmethod
    async def complete(self, messages: Sequence[LLMMessage]) -> LLMResponse: ...

    @abstractmethod
    async def complete_structured[T: BaseModel](
        self,
        request: LLMRequest,
        schema: type[T],
    ) -> StructuredResponse[T]: ...

    @abstractmethod
    async def ping(self) -> bool: ...

    @abstractmethod
    async def close(self) -> None: ...
