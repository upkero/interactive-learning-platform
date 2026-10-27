"""OpenAICompatibleLLMClient unit tests: json_schema mode, parts, errors, usage."""

from types import SimpleNamespace
from typing import Any

import httpx
import openai
import pytest
from pydantic import BaseModel, SecretStr

from src.app.contracts.llm.image_part import ImagePart
from src.app.contracts.llm.llm_message import LLMMessage
from src.app.contracts.llm.llm_request import LLMRequest
from src.app.contracts.llm.structured_response import TokenUsage
from src.app.contracts.llm.system_block import SystemBlock
from src.app.contracts.llm.text_part import TextPart
from src.app.core.settings.llm import LLMSettings
from src.app.exceptions.llm import LLMGenerationError, LLMRateLimitError, LLMSchemaError
from src.app.llm.openai_compatible_llm_client import OpenAICompatibleLLMClient

_TEST_URL = "http://localhost:11434/v1/chat/completions"


class _Picked(BaseModel):
    count: int


class _FakeCompletions:
    def __init__(self, owner: "_FakeOpenAI") -> None:
        self._owner = owner

    async def create(self, **kwargs: object) -> SimpleNamespace:
        self._owner.create_calls.append(kwargs)
        if self._owner.create_error is not None:
            raise self._owner.create_error
        result = self._owner.create_result
        assert result is not None
        return result


class _FakeChat:
    def __init__(self, owner: "_FakeOpenAI") -> None:
        self.completions = _FakeCompletions(owner)


class _FakeModels:
    async def list(self) -> list[object]:
        return []


class _FakeOpenAI:
    def __init__(self) -> None:
        self.chat = _FakeChat(self)
        self.models = _FakeModels()
        self.create_calls: list[dict[str, object]] = []
        self.create_error: BaseException | None = None
        self.create_result: SimpleNamespace | None = None
        self.closed = False

    async def close(self) -> None:
        self.closed = True


def _fake_openai(result: SimpleNamespace | None = None, error: BaseException | None = None) -> _FakeOpenAI:
    fake = _FakeOpenAI()
    fake.create_result = result
    fake.create_error = error
    return fake


def _client(fake: _FakeOpenAI, **settings_kwargs: Any) -> OpenAICompatibleLLMClient:
    settings = LLMSettings(provider="openai_compatible", api_key=SecretStr("k"), model="m", **settings_kwargs)
    return OpenAICompatibleLLMClient(settings=settings, client=fake)  # type: ignore[arg-type]


def _completion(*, content: str | None, cached: int = 2) -> SimpleNamespace:
    return SimpleNamespace(
        id="cmp_1",
        created=17,
        model="m",
        choices=[SimpleNamespace(message=SimpleNamespace(content=content), finish_reason="stop")],
        usage=SimpleNamespace(
            prompt_tokens=3,
            completion_tokens=5,
            total_tokens=8,
            prompt_tokens_details=SimpleNamespace(cached_tokens=cached),
        ),
    )


def _rate_limit_error() -> openai.RateLimitError:
    return openai.RateLimitError(
        "rate limited",
        response=httpx.Response(429, request=httpx.Request("POST", _TEST_URL)),
        body=None,
    )


@pytest.mark.unit
async def test_structured_builds_json_schema_and_maps_parts() -> None:
    fake = _fake_openai(result=_completion(content='{"count": 7}'))
    request = LLMRequest(
        purpose="quiz_gen",
        messages=(LLMMessage(role="user", content=(TextPart(text="A"), ImagePart("image/jpeg", "B="))),),
        system=(SystemBlock(text="rules"),),
        max_tokens=512,
        temperature=0.3,
    )

    response = await _client(fake).complete_structured(request, _Picked)

    kwargs = fake.create_calls[0]
    assert kwargs["response_format"] == {
        "type": "json_schema",
        "json_schema": {"name": "_Picked", "schema": _Picked.model_json_schema()},
    }
    assert kwargs["max_tokens"] == 512
    assert kwargs["temperature"] == 0.3
    assert kwargs["messages"] == [
        {"role": "system", "content": "rules"},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "A"},
                {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,B="}},
            ],
        },
    ]
    assert response.value == _Picked(count=7)
    assert response.usage == TokenUsage(input_tokens=3, output_tokens=5, cache_read_input_tokens=2)


@pytest.mark.unit
async def test_structured_omits_temperature_when_none() -> None:
    fake = _fake_openai(result=_completion(content='{"count": 1}'))
    request = LLMRequest(purpose="rerank", messages=(LLMMessage(role="user", content="q"),), temperature=None)

    await _client(fake).complete_structured(request, _Picked)

    assert "temperature" not in fake.create_calls[0]


@pytest.mark.unit
async def test_structured_empty_content_raises_schema_error() -> None:
    fake = _fake_openai(result=_completion(content=None))

    with pytest.raises(LLMSchemaError):
        await _client(fake).complete_structured(
            LLMRequest(purpose="describe", messages=(LLMMessage(role="user", content="q"),)),
            _Picked,
        )


@pytest.mark.unit
async def test_structured_invalid_json_raises_schema_error() -> None:
    fake = _fake_openai(result=_completion(content="not a json"))

    with pytest.raises(LLMSchemaError):
        await _client(fake).complete_structured(
            LLMRequest(purpose="judge", messages=(LLMMessage(role="user", content="q"),)),
            _Picked,
        )


@pytest.mark.unit
async def test_structured_rate_limit_maps() -> None:
    fake = _fake_openai(error=_rate_limit_error())

    with pytest.raises(LLMRateLimitError):
        await _client(fake).complete_structured(
            LLMRequest(purpose="topics", messages=(LLMMessage(role="user", content="q"),)),
            _Picked,
        )


@pytest.mark.unit
async def test_structured_openai_error_maps_to_generation() -> None:
    fake = _fake_openai(error=openai.APIConnectionError(request=httpx.Request("POST", _TEST_URL)))

    with pytest.raises(LLMGenerationError):
        await _client(fake).complete_structured(
            LLMRequest(purpose="merge_confirm", messages=(LLMMessage(role="user", content="q"),)),
            _Picked,
        )


@pytest.mark.unit
async def test_plain_complete_success_and_rate_limit() -> None:
    fake = _fake_openai(result=_completion(content="answer"))
    client = _client(fake)

    response = await client.complete((LLMMessage(role="user", content="q"),))
    assert response.content == "answer"
    assert response.usage == {"prompt_tokens": 3, "completion_tokens": 5, "total_tokens": 8}

    fake.create_error = _rate_limit_error()
    with pytest.raises(LLMRateLimitError):
        await client.complete((LLMMessage(role="user", content="q"),))


@pytest.mark.unit
async def test_ping_and_close() -> None:
    fake = _fake_openai(result=_completion(content="x"))
    client = _client(fake)

    assert await client.ping() is True
    assert fake.closed is False
    await client.close()
    assert fake.closed is True
