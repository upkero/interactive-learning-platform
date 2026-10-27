"""ClaudeClient unit tests on a fake SDK: mapping, image parts, cache hints, errors."""

import anthropic
import httpx
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
from src.app.llm.claude_client import ClaudeClient

_ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"


class _Draft(BaseModel):
    title: str


class _FakeBlock:
    def __init__(self, text: str) -> None:
        self.text = text


class _FakeUsage:
    def __init__(
        self,
        *,
        input_tokens: int = 10,
        output_tokens: int = 20,
        cache_read: int = 0,
        cache_creation: int = 0,
    ) -> None:
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.cache_read_input_tokens = cache_read
        self.cache_creation_input_tokens = cache_creation


class _FakeParseResult:
    def __init__(self, *, parsed_output: object, usage: object) -> None:
        self.parsed_output = parsed_output
        self.usage = usage


class _FakeCreateResult:
    def __init__(self, *, content: list[object], usage: object) -> None:
        self.content = content
        self.usage = usage
        self.model = "claude-x"
        self.stop_reason = "end_turn"


class _FakeMessages:
    def __init__(self, owner: "_FakeSDK") -> None:
        self._owner = owner

    async def parse(self, **kwargs: object) -> _FakeParseResult:
        self._owner.parse_calls.append(kwargs)
        if self._owner.parse_error is not None:
            raise self._owner.parse_error
        assert self._owner.parse_result is not None
        return self._owner.parse_result

    async def create(self, **kwargs: object) -> _FakeCreateResult:
        self._owner.create_calls.append(kwargs)
        if self._owner.create_error is not None:
            raise self._owner.create_error
        assert self._owner.create_result is not None
        return self._owner.create_result


class _FakeModels:
    def __init__(self, owner: "_FakeSDK") -> None:
        self._owner = owner

    async def list(self) -> list[object]:
        if self._owner.models_error is not None:
            raise self._owner.models_error
        return []


class _FakeSDK:
    def __init__(self) -> None:
        self.messages = _FakeMessages(self)
        self.models = _FakeModels(self)
        self.parse_calls: list[dict[str, object]] = []
        self.create_calls: list[dict[str, object]] = []
        self.parse_error: BaseException | None = None
        self.parse_result: _FakeParseResult | None = None
        self.create_error: BaseException | None = None
        self.create_result: _FakeCreateResult | None = None
        self.models_error: BaseException | None = None
        self.closed = False

    async def close(self) -> None:
        self.closed = True


def _client(sdk: _FakeSDK) -> ClaudeClient:
    settings = LLMSettings(provider="anthropic", api_key=SecretStr("sk"), model="claude-x")
    return ClaudeClient(settings=settings, client=sdk)  # type: ignore[arg-type]


def _rate_limit_error() -> anthropic.RateLimitError:
    return anthropic.RateLimitError(
        "rate limited",
        response=httpx.Response(429, request=httpx.Request("POST", _ANTHROPIC_URL)),
        body=None,
    )


def _api_error() -> anthropic.APIError:
    return anthropic.APIError("boom", httpx.Request("POST", _ANTHROPIC_URL), body=None)


@pytest.mark.unit
async def test_structured_maps_messages_parts_and_cache() -> None:
    sdk = _FakeSDK()
    draft = _Draft(title="draft")
    sdk.parse_result = _FakeParseResult(
        parsed_output=draft,
        usage=_FakeUsage(input_tokens=10, output_tokens=5, cache_read=2, cache_creation=1),
    )
    request = LLMRequest(
        purpose="main_pass",
        messages=(
            LLMMessage(
                role="user",
                content=(TextPart(text="A"), ImagePart(media_type="image/png", data_base64="AAAA")),
            ),
        ),
        system=(SystemBlock(text="immutable"), SystemBlock(text="volatile", cache=True)),
        max_tokens=100,
    )

    response = await _client(sdk).complete_structured(request, _Draft)

    parse_kwargs = sdk.parse_calls[0]
    assert parse_kwargs["model"] == "claude-x"
    assert parse_kwargs["max_tokens"] == 100
    assert parse_kwargs["output_format"] is _Draft
    assert parse_kwargs["system"] == [
        {"type": "text", "text": "immutable"},
        {"type": "text", "text": "volatile", "cache_control": {"type": "ephemeral"}},
    ]
    assert parse_kwargs["messages"] == [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "A"},
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/png", "data": "AAAA"},
                },
            ],
        },
    ]
    assert response.value == draft
    assert response.usage == TokenUsage(
        input_tokens=10,
        output_tokens=5,
        cache_read_input_tokens=2,
        cache_creation_input_tokens=1,
    )


@pytest.mark.unit
async def test_structured_str_content_passes_through() -> None:
    sdk = _FakeSDK()
    sdk.parse_result = _FakeParseResult(
        parsed_output=_Draft(title="x"),
        usage=_FakeUsage(cache_read=1, cache_creation=0),
    )
    request = LLMRequest(
        purpose="quiz_verify",
        messages=(LLMMessage(role="assistant", content="hi"),),
        system=(SystemBlock(text="s"),),
    )

    response = await _client(sdk).complete_structured(request, _Draft)

    parse_kwargs = sdk.parse_calls[0]
    assert parse_kwargs["messages"] == [{"role": "assistant", "content": "hi"}]
    assert parse_kwargs["system"] == [{"type": "text", "text": "s"}]
    assert response.value == _Draft(title="x")


@pytest.mark.unit
async def test_missing_parsed_output_raises_schema_error() -> None:
    sdk = _FakeSDK()
    sdk.parse_result = _FakeParseResult(parsed_output=None, usage=_FakeUsage())

    with pytest.raises(LLMSchemaError):
        await _client(sdk).complete_structured(
            LLMRequest(purpose="main_pass", messages=(LLMMessage(role="user", content="q"),)),
            _Draft,
        )
    assert len(sdk.parse_calls) == 1


@pytest.mark.unit
async def test_rate_limit_maps_to_our_exception() -> None:
    sdk = _FakeSDK()
    sdk.parse_error = _rate_limit_error()

    with pytest.raises(LLMRateLimitError):
        await _client(sdk).complete_structured(
            LLMRequest(purpose="rerank", messages=(LLMMessage(role="user", content="q"),)),
            _Draft,
        )
    assert sdk.parse_error is not None


@pytest.mark.unit
async def test_sdk_error_maps_to_generation_error() -> None:
    sdk = _FakeSDK()
    sdk.parse_error = _api_error()

    with pytest.raises(LLMGenerationError):
        await _client(sdk).complete_structured(
            LLMRequest(purpose="codegen", messages=(LLMMessage(role="user", content="q"),)),
            _Draft,
        )


@pytest.mark.unit
async def test_plain_complete_joins_text_and_usage() -> None:
    sdk = _FakeSDK()
    sdk.create_result = _FakeCreateResult(
        content=[_FakeBlock("Hi "), _FakeBlock("there")],
        usage=_FakeUsage(input_tokens=11, output_tokens=4, cache_read=3, cache_creation=0),
    )

    response = await _client(sdk).complete((LLMMessage(role="user", content="hello"),))

    create_kwargs = sdk.create_calls[0]
    assert create_kwargs["model"] == "claude-x"
    assert create_kwargs["messages"] == [{"role": "user", "content": "hello"}]
    assert response.content == "Hi there"
    assert response.model == "claude-x"
    assert response.finish_reason == "end_turn"
    assert response.usage == {
        "input_tokens": 11,
        "output_tokens": 4,
        "cache_read_input_tokens": 3,
        "cache_creation_input_tokens": 0,
    }


@pytest.mark.unit
async def test_plain_rate_limit_maps() -> None:
    sdk = _FakeSDK()
    sdk.create_error = _rate_limit_error()

    with pytest.raises(LLMRateLimitError):
        await _client(sdk).complete((LLMMessage(role="user", content="hello"),))


@pytest.mark.unit
async def test_ping_true_and_false() -> None:
    sdk = _FakeSDK()
    assert await _client(sdk).ping() is True

    sdk2 = _FakeSDK()
    sdk2.models_error = _api_error()
    assert await _client(sdk2).ping() is False


@pytest.mark.unit
async def test_close_delegates() -> None:
    sdk = _FakeSDK()
    client = _client(sdk)
    await client.close()
    assert sdk.closed is True
