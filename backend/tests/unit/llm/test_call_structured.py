"""call_structured unit tests: schema retry semantics on FakeLLMClient."""

import pytest
from pydantic import BaseModel

from src.app.contracts.llm.llm_message import LLMMessage
from src.app.contracts.llm.llm_request import LLMRequest
from src.app.contracts.llm.structured_response import StructuredResponse
from src.app.exceptions.llm import LLMGenerationError, LLMSchemaError
from src.app.llm.structured import call_structured
from tests.support.fakes.llm.llm_client import FakeLLMClient


class _Draft(BaseModel):
    count: int


def _request() -> LLMRequest:
    return LLMRequest(purpose="main_pass", messages=(LLMMessage(role="user", content="go"),))


@pytest.mark.unit
async def test_success_needs_single_call() -> None:
    fake = FakeLLMClient(responses=[StructuredResponse(_Draft(count=1))])

    result = await call_structured(fake, _request(), _Draft)

    assert result == _Draft(count=1)
    assert len(fake.structured_calls) == 1


@pytest.mark.unit
async def test_schema_error_triggers_exactly_one_retry() -> None:
    fake = FakeLLMClient(
        responses=[LLMSchemaError("bad json"), StructuredResponse(_Draft(count=2))],
    )

    result = await call_structured(fake, _request(), _Draft)

    assert result == _Draft(count=2)
    assert len(fake.structured_calls) == 2

    retry_request = fake.structured_calls[1].request
    original_messages = fake.structured_calls[0].request.messages
    assert retry_request.messages[:-1] == original_messages
    hint = retry_request.messages[-1].content
    assert isinstance(hint, str)
    assert "Ответ не прошёл проверку схемы: bad json" in hint


@pytest.mark.unit
async def test_permanent_schema_error_raises_after_last_retry() -> None:
    fake = FakeLLMClient(responses=[LLMSchemaError("bad 1"), LLMSchemaError("bad 2")])

    with pytest.raises(LLMSchemaError, match="bad 2"):
        await call_structured(fake, _request(), _Draft)

    assert len(fake.structured_calls) == 2


@pytest.mark.unit
async def test_non_schema_errors_are_not_retried() -> None:
    fake = FakeLLMClient(responses=[LLMGenerationError("network"), StructuredResponse(_Draft(count=3))])

    with pytest.raises(LLMGenerationError):
        await call_structured(fake, _request(), _Draft)

    assert len(fake.structured_calls) == 1


@pytest.mark.unit
async def test_custom_retries_zero_disables_retry() -> None:
    fake = FakeLLMClient(responses=[LLMSchemaError("bad")])

    with pytest.raises(LLMSchemaError):
        await call_structured(fake, _request(), _Draft, retries=0)

    assert len(fake.structured_calls) == 1
