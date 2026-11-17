"""call_structured unit tests: schema retry semantics on FakeLLMClient."""

import pytest
from pydantic import BaseModel

from src.app.contracts.llm.llm_message import LLMMessage
from src.app.contracts.llm.llm_request import LLMRequest
from src.app.exceptions.llm import LLMGenerationError, LLMSchemaError
from src.app.llm.prompts import SCHEMA_RETRY_PROMPT
from src.app.llm.structured import call_structured
from tests.support.fakes.llm.llm_client import FakeLLMClient

pytestmark = pytest.mark.unit


class _Draft(BaseModel):
    count: int


def _request() -> LLMRequest:
    return LLMRequest(purpose="main_pass", messages=(LLMMessage(role="user", content="go"),))


async def test_success_needs_single_call() -> None:
    fake = FakeLLMClient(structured=[_Draft(count=1)])

    result = await call_structured(fake, _request(), _Draft)

    assert result == _Draft(count=1)
    assert len(fake.requests) == 1


async def test_schema_error_triggers_exactly_one_retry() -> None:
    broken = '{"count": '
    fake = FakeLLMClient(structured=[LLMSchemaError("bad json", raw_output=broken), _Draft(count=2)])

    result = await call_structured(fake, _request(), _Draft)

    assert result == _Draft(count=2)
    assert len(fake.requests) == 2

    retry_messages = fake.requests[1].messages
    # The model sees its own broken reply as the last assistant message and
    # the correction hint as one more user message.
    assert retry_messages[:-2] == _request().messages
    assert retry_messages[-2].role == "assistant"
    assert retry_messages[-2].content == broken
    hint = retry_messages[-1].content
    assert isinstance(hint, str)
    assert SCHEMA_RETRY_PROMPT.format(error="bad json") in hint


async def test_permanent_schema_error_raises_after_last_retry() -> None:
    fake = FakeLLMClient(structured=[LLMSchemaError("bad 1"), LLMSchemaError("bad 2")])

    with pytest.raises(LLMSchemaError, match="bad 2"):
        await call_structured(fake, _request(), _Draft)

    assert len(fake.requests) == 2


async def test_non_schema_errors_are_not_retried() -> None:
    fake = FakeLLMClient(structured=[LLMGenerationError("network"), _Draft(count=3)])

    with pytest.raises(LLMGenerationError):
        await call_structured(fake, _request(), _Draft)

    assert len(fake.requests) == 1


async def test_custom_retries_zero_disables_retry() -> None:
    fake = FakeLLMClient(structured=[LLMSchemaError("bad")])

    with pytest.raises(LLMSchemaError):
        await call_structured(fake, _request(), _Draft, retries=0)

    assert len(fake.requests) == 1
