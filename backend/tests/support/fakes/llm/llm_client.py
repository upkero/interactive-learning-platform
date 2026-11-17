"""Fake LLMClient for unit tests, per the test-double contract:

scripted answer queues (``structured`` for complete_structured,
``completions`` for plain complete), every complete_structured request
recorded in ``requests``, exceptions raised as scripted. A call with an
empty queue or an answer that does not fit the requested schema fails
with AssertionError — tests fail loudly instead of returning None.
"""

from collections.abc import Sequence

from pydantic import BaseModel

from src.app.contracts.llm.llm_message import LLMMessage
from src.app.contracts.llm.llm_request import LLMRequest
from src.app.contracts.llm.llm_response import LLMResponse
from src.app.contracts.llm.structured_response import StructuredResponse
from src.app.contracts.llm.token_usage import TokenUsage
from src.app.interfaces.llm.llm_client import LLMClient


class FakeLLMClient(LLMClient):
    """Scripted queues of pre-defined answers, per the fakes contract.

    ``structured`` holds pydantic objects (or exceptions to raise) and feeds
    ``complete_structured``; ``completions`` holds ``LLMResponse`` (or
    exceptions) and feeds plain ``complete``. ``usage`` is reported with
    every structured answer — a fake cannot know real token counts, so the
    test pins them once.
    """

    def __init__(
        self,
        *,
        structured: Sequence[BaseModel | BaseException] = (),
        completions: Sequence[LLMResponse | BaseException] = (),
        usage: TokenUsage | None = None,
        model_name: str = "fake-model",
        provider_name: str = "fake",
        ping_result: bool = True,
    ) -> None:
        self._structured: list[BaseModel | BaseException] = list(structured)
        self._completions: list[LLMResponse | BaseException] = list(completions)
        self._usage = usage
        self._model_name = model_name
        self._provider_name = provider_name
        self._ping_result = ping_result
        self.requests: list[LLMRequest] = []
        self.complete_messages: list[tuple[LLMMessage, ...]] = []
        self.pinged = False
        self.closed = False

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def provider_name(self) -> str:
        return self._provider_name

    async def complete(self, messages: Sequence[LLMMessage]) -> LLMResponse:
        self.complete_messages.append(tuple(messages))
        response = self._next_completion()
        return response

    async def complete_structured[T: BaseModel](
        self,
        request: LLMRequest,
        schema: type[T],
    ) -> StructuredResponse[T]:
        self.requests.append(request)
        item = self._next_structured()
        if not isinstance(item, schema):
            raise AssertionError(
                f"FakeLLMClient: scripted answer {type(item).__name__} does not match schema {schema.__name__}."
            )
        return StructuredResponse(value=item, usage=self._usage)

    async def ping(self) -> bool:
        self.pinged = True
        return self._ping_result

    async def close(self) -> None:
        self.closed = True

    def _next_structured(self) -> BaseModel:
        if not self._structured:
            raise AssertionError("FakeLLMClient: no scripted structured answers left.")
        item = self._structured.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item

    def _next_completion(self) -> LLMResponse:
        if not self._completions:
            raise AssertionError("FakeLLMClient: no scripted completions left.")
        item = self._completions.pop(0)
        if isinstance(item, BaseException):
            raise item
        assert isinstance(item, LLMResponse), "FakeLLMClient: completions queue accepts LLMResponse only."
        return item
