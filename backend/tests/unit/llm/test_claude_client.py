"""ClaudeClient unit tests against the real Anthropic SDK over a mocked HTTP transport.

No hand-made SDK fakes: the transport replays canned responses, so the tests
exercise the real request mapping (system blocks with cache_control, image
blocks, no temperature) and the real error mapping (broken JSON, truncation,
refusal, 429, 500).
"""

import json
from typing import Any

import httpx2
import pytest
from anthropic import AsyncAnthropic
from pydantic import BaseModel, SecretStr

from src.app.contracts.llm.image_part import ImagePart
from src.app.contracts.llm.llm_message import LLMMessage
from src.app.contracts.llm.llm_request import LLMRequest
from src.app.contracts.llm.llm_response import LLMResponse
from src.app.contracts.llm.structured_response import TokenUsage
from src.app.contracts.llm.system_block import SystemBlock
from src.app.contracts.llm.text_part import TextPart
from src.app.core.settings.llm import LLMSettings
from src.app.exceptions.llm import LLMGenerationError, LLMRateLimitError, LLMSchemaError
from src.app.llm.claude_client import ClaudeClient


class _Draft(BaseModel):
    title: str = "ok"


def _settings() -> LLMSettings:
    return LLMSettings(
        provider="anthropic",
        api_key=SecretStr("test-key"),
        model="claude-sonnet-5-5",
        _env_file=None,
    )


def _sdk(
    handler: Any,
) -> tuple[ClaudeClient, httpx2.AsyncClient]:
    http_client = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    sdk = AsyncAnthropic(api_key="test-key", max_retries=0, http_client=http_client)
    return ClaudeClient(settings=_settings(), client=sdk), http_client


def _replaying(response: httpx2.Response, captured: list[httpx2.Request]) -> Any:
    def handler(request: httpx2.Request) -> httpx2.Response:
        captured.append(request)
        return response

    return handler


def _message_response(
    *,
    text: str = '{"title": "ok"}',
    stop_reason: str = "end_turn",
    usage: dict[str, Any] | None = None,
    content: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "id": "msg_1",
        "type": "message",
        "role": "assistant",
        "model": "claude-sonnet-5-5",
        "content": content if content is not None else [{"type": "text", "text": text}],
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": usage
        or {
            "input_tokens": 10,
            "output_tokens": 5,
            "cache_read_input_tokens": 2,
            "cache_creation_input_tokens": 1,
        },
    }


def _request(**overrides: Any) -> LLMRequest:
    base: dict[str, Any] = {
        "purpose": "main_pass",
        "messages": (LLMMessage(role="user", content="draft a page"),),
    }
    base.update(overrides)
    return LLMRequest(**base)


_ERROR_BODY = {"type": "error", "error": {"type": "api_error", "message": "Internal error."}}


@pytest.mark.unit
async def test_structured_success_parses_value_and_usage() -> None:
    captured: list[httpx2.Request] = []
    client, _ = _sdk(_replaying(httpx2.Response(200, json=_message_response()), captured))

    response = await client.complete_structured(
        _request(system=(SystemBlock("shared context", cache=True), SystemBlock("volatile part"))),
        _Draft,
    )

    assert response.value == _Draft()
    assert response.usage == TokenUsage(
        input_tokens=10, output_tokens=5, cache_read_input_tokens=2, cache_creation_input_tokens=1
    )


@pytest.mark.unit
async def test_structured_request_body_maps_system_blocks_and_schema() -> None:
    captured: list[httpx2.Request] = []
    client, _ = _sdk(_replaying(httpx2.Response(200, json=_message_response()), captured))

    await client.complete_structured(
        _request(system=(SystemBlock("shared context", cache=True), SystemBlock("volatile part"))),
        _Draft,
    )

    body = json.loads(captured[0].content)
    assert body["system"] == [
        {"type": "text", "text": "shared context", "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": "volatile part"},
    ]
    assert body["output_config"]["format"]["type"] == "json_schema"
    assert body["output_config"]["format"]["schema"]["properties"]["title"]["type"] == "string"
    # Sampling parameters are never sent to Claude (see claude_client docstring).
    assert "temperature" not in body


@pytest.mark.unit
async def test_structured_request_body_maps_image_blocks() -> None:
    captured: list[httpx2.Request] = []
    client, _ = _sdk(_replaying(httpx2.Response(200, json=_message_response()), captured))
    content: tuple[TextPart | ImagePart, ...] = (
        ImagePart(media_type="image/png", data_base64="QUJD"),
        TextPart(text="describe this"),
    )

    await client.complete_structured(_request(messages=(LLMMessage(role="user", content=content),)), _Draft)

    body = json.loads(captured[0].content)
    blocks = body["messages"][0]["content"]
    assert blocks[0] == {
        "type": "image",
        "source": {"type": "base64", "media_type": "image/png", "data": "QUJD"},
    }
    assert blocks[1] == {"type": "text", "text": "describe this"}


@pytest.mark.unit
async def test_structured_broken_json_raises_schema_error() -> None:
    # On the pre-review code this path raised the raw SDK ValidationError;
    # now it must become LLMSchemaError so call_structured can retry.
    captured: list[httpx2.Request] = []
    client, _ = _sdk(_replaying(httpx2.Response(200, json=_message_response(text="not json at all")), captured))

    with pytest.raises(LLMSchemaError):
        await client.complete_structured(_request(), _Draft)


@pytest.mark.unit
async def test_structured_truncated_output_raises_schema_error() -> None:
    captured: list[httpx2.Request] = []
    client, _ = _sdk(
        _replaying(
            httpx2.Response(200, json=_message_response(text='{"title": "unclosed', stop_reason="max_tokens")),
            captured,
        )
    )

    with pytest.raises(LLMSchemaError, match="max_tokens"):
        await client.complete_structured(_request(), _Draft)


@pytest.mark.unit
async def test_structured_refusal_raises_generation_error() -> None:
    captured: list[httpx2.Request] = []
    client, _ = _sdk(
        _replaying(httpx2.Response(200, json=_message_response(text="no.", stop_reason="refusal")), captured)
    )

    with pytest.raises(LLMGenerationError):
        await client.complete_structured(_request(), _Draft)


@pytest.mark.unit
async def test_structured_rate_limit_is_mapped() -> None:
    captured: list[httpx2.Request] = []
    client, _ = _sdk(
        _replaying(
            httpx2.Response(
                429,
                json={"type": "error", "error": {"type": "rate_limit_error", "message": "slow down"}},
            ),
            captured,
        )
    )

    with pytest.raises(LLMRateLimitError):
        await client.complete_structured(_request(), _Draft)


@pytest.mark.unit
async def test_structured_500_is_mapped_to_generation_error() -> None:
    captured: list[httpx2.Request] = []
    client, _ = _sdk(_replaying(httpx2.Response(500, json=_ERROR_BODY), captured))

    with pytest.raises(LLMGenerationError):
        await client.complete_structured(_request(), _Draft)


@pytest.mark.unit
async def test_plain_complete_returns_text_and_usage_mapping() -> None:
    captured: list[httpx2.Request] = []
    client, _ = _sdk(_replaying(httpx2.Response(200, json=_message_response(text="hello")), captured))

    response = await client.complete((LLMMessage(role="user", content="hi"),))

    assert isinstance(response, LLMResponse)
    assert response.content == "hello"
    assert response.model == "claude-sonnet-5-5"
    assert response.finish_reason == "end_turn"
    assert response.usage == {
        "input_tokens": 10,
        "output_tokens": 5,
        "cache_read_input_tokens": 2,
        "cache_creation_input_tokens": 1,
    }
    body = json.loads(captured[0].content)
    assert "temperature" not in body


@pytest.mark.unit
async def test_plain_complete_empty_content_raises_generation_error() -> None:
    captured: list[httpx2.Request] = []
    client, _ = _sdk(_replaying(httpx2.Response(200, json=_message_response(content=[])), captured))

    with pytest.raises(LLMGenerationError):
        await client.complete((LLMMessage(role="user", content="hi"),))


@pytest.mark.unit
async def test_ping_true_on_200() -> None:
    client, _ = _sdk(_replaying(httpx2.Response(200, json={"data": [], "has_more": False}), []))

    assert await client.ping() is True


@pytest.mark.unit
async def test_ping_false_on_500() -> None:
    client, _ = _sdk(_replaying(httpx2.Response(500, json=_ERROR_BODY), []))

    assert await client.ping() is False


@pytest.mark.unit
async def test_close_closes_the_sdk_http_client() -> None:
    client, http_client = _sdk(_replaying(httpx2.Response(200, json=_message_response()), []))

    await client.close()

    assert http_client.is_closed
