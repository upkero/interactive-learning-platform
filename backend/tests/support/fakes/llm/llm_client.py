"""Fake LLMClient for unit tests: scripted answers, call recording."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from src.app.contracts.llm.llm_message import LLMMessage
from src.app.contracts.llm.llm_request import LLMRequest
from src.app.contracts.llm.llm_response import LLMResponse
from src.app.contracts.llm.structured_response import StructuredResponse
from src.app.interfaces.llm.llm_client import LLMClient


@dataclass(frozen=True)
class CompleteCall:
    messages: tuple[LLMMessage, ...]


@dataclass(frozen=True)
class StructuredCall:
    request: LLMRequest
    schema: type[BaseModel]


class FakeLLMClient(LLMClient):
    """Returns scripted ``responses`` one-by-one; base exceptions are raised."""

    def __init__(
        self,
        *,
        responses: Sequence[LLMResponse | StructuredResponse[Any] | BaseException] = (),
        model_name: str = "fake-model",
        provider_name: str = "fake",
        ping_result: bool = True,
    ) -> None:
        self._responses: list[LLMResponse | StructuredResponse[Any] | BaseException] = list(responses)
        self._model_name = model_name
        self._provider_name = provider_name
        self._ping_result = ping_result
        self.complete_calls: list[CompleteCall] = []
        self.structured_calls: list[StructuredCall] = []
        self.pinged = False
        self.closed = False

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def provider_name(self) -> str:
        return self._provider_name

    async def complete(self, messages: Sequence[LLMMessage]) -> LLMResponse:
        self.complete_calls.append(CompleteCall(tuple(messages)))
        response = self._next()
        assert isinstance(response, LLMResponse)
        return response

    async def complete_structured[T: BaseModel](
        self,
        request: LLMRequest,
        schema: type[T],
    ) -> StructuredResponse[T]:
        self.structured_calls.append(StructuredCall(request=request, schema=schema))
        response = self._next()
        assert isinstance(response, StructuredResponse)
        return response  # type: ignore[return-value]

    async def ping(self) -> bool:
        self.pinged = True
        return self._ping_result

    async def close(self) -> None:
        self.closed = True

    def _next(self) -> LLMResponse | StructuredResponse[Any]:
        if not self._responses:
            raise AssertionError("FakeLLMClient: no scripted responses left.")
        item = self._responses.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item
