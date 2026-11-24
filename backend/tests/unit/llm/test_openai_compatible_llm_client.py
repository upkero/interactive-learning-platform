"""OpenAI-compatible client unit tests against the real SDK over a mocked HTTP transport.

The transport replays canned responses, so the tests exercise the real
request body (json_schema response_format with strict mode, system first,
image_url parts, temperature passthrough) and real error mapping
(broken JSON, empty content, 429, 500, timeout).
"""

import json
import logging
from pathlib import Path
from typing import Any

import httpx2
import pytest
from openai import AsyncOpenAI
from pydantic import BaseModel, SecretStr

from evals.usage_report import read_summaries, write_report
from src.app.contracts.llm.image_part import ImagePart
from src.app.contracts.llm.llm_message import LLMMessage
from src.app.contracts.llm.llm_request import LLMRequest
from src.app.contracts.llm.system_block import SystemBlock
from src.app.contracts.llm.text_part import TextPart
from src.app.contracts.llm.token_usage import TokenUsage
from src.app.core.settings.llm import LLMSettings
from src.app.exceptions.llm import (
    LLMGenerationError,
    LLMOutputTruncatedError,
    LLMRateLimitError,
    LLMSchemaError,
    LLMTimeoutError,
)
from src.app.llm.instrumented_llm_client import InstrumentedLLMClient
from src.app.llm.openai_compatible_llm_client import OpenAICompatibleLLMClient
from src.app.observability.usage_tracker import UsageTracker, bind_usage_tracker
from tests.support.fakes.observability.metrics_collector import RecordingMetricsCollector

pytestmark = pytest.mark.unit


class _Draft(BaseModel):
    title: str = "ok"


_BASE_URL = "http://test/v1"


def _settings(**overrides: Any) -> LLMSettings:
    base: dict[str, Any] = {
        "provider": "openai_compatible",
        "api_key": SecretStr("test-key"),
        "model": "llama3.2",
        "base_url": _BASE_URL,
        "_env_file": None,
    }
    base.update(overrides)
    return LLMSettings(**base)


def _client(handler: Any) -> tuple[OpenAICompatibleLLMClient, httpx2.AsyncClient]:
    http_client = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    sdk = AsyncOpenAI(api_key="test-key", base_url=_BASE_URL, max_retries=0, http_client=http_client)
    return OpenAICompatibleLLMClient(settings=_settings(), client=sdk), http_client


def _replaying(response: httpx2.Response, captured: list[httpx2.Request]) -> Any:
    def handler(request: httpx2.Request) -> httpx2.Response:
        captured.append(request)
        return response

    return handler


def _completion_response(
    *,
    content: str | None = '{"title": "ok"}',
    usage: dict[str, Any] | None = None,
    model: str = "llama3.2",
    finish_reason: str = "stop",
) -> dict[str, Any]:
    return {
        "id": "chatcmpl-1",
        "object": "chat.completion",
        "created": 1700000000,
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": finish_reason,
            }
        ],
        "usage": usage
        or {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
            "prompt_tokens_details": {"cached_tokens": 2},
        },
    }


def _request(**overrides: Any) -> LLMRequest:
    base: dict[str, Any] = {
        "purpose": "main_pass",
        "messages": (LLMMessage(role="user", content="draft a page"),),
    }
    base.update(overrides)
    return LLMRequest(**base)


_ERROR_BODY = {"error": {"message": "boom", "type": "server_error", "code": None}}


async def test_structured_success_parses_value_and_usage() -> None:
    captured: list[httpx2.Request] = []
    client, _ = _client(_replaying(httpx2.Response(200, json=_completion_response()), captured))

    response = await client.complete_structured(_request(), _Draft)

    assert response.value == _Draft()
    assert response.usage == TokenUsage(
        input_tokens=8, output_tokens=5, cache_read_input_tokens=2, cache_creation_input_tokens=0
    )


async def test_cache_read_and_write_are_disjoint_in_summary_and_metrics() -> None:
    usage = {
        "prompt_tokens": 1000,
        "completion_tokens": 0,
        "total_tokens": 1000,
        "prompt_tokens_details": {"cached_tokens": 800, "cache_write_tokens": 100},
    }
    handler = _replaying(httpx2.Response(200, json=_completion_response(usage=usage)), [])
    http_client = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    sdk = AsyncOpenAI(api_key="test-key", base_url=_BASE_URL, max_retries=0, http_client=http_client)
    client = OpenAICompatibleLLMClient(settings=_settings(model="anthropic/claude-sonnet-5.5"), client=sdk)
    metrics = RecordingMetricsCollector()
    wrapped = InstrumentedLLMClient(client=client, logger=logging.getLogger("test.llm"), metrics=metrics)
    tracker = UsageTracker(part_id="p", document_id="d")
    with bind_usage_tracker(tracker):
        response = await wrapped.complete_structured(_request(), _Draft)
    assert response.usage == TokenUsage(100, 0, 800, 100)
    assert tracker.summary().cost_usd == 0.00053
    assert tracker.summary().usage["main_pass"] == {"input": 100, "output": 0, "cache_read": 800, "cache_write": 100}
    for field, value in (("input_tokens", 100), ("cache_read_input_tokens", 800), ("cache_creation_input_tokens", 100)):
        assert metrics.histograms_named(f"llm.complete.usage.{field}")[0].value == value


async def test_cache_reads_cannot_exceed_prompt_tokens() -> None:
    usage = {
        "prompt_tokens": 10,
        "completion_tokens": 1,
        "total_tokens": 11,
        "prompt_tokens_details": {"cached_tokens": 11},
    }
    client, _ = _client(_replaying(httpx2.Response(200, json=_completion_response(usage=usage)), []))
    with pytest.raises(LLMGenerationError, match="inconsistent cache usage"):
        await client.complete_structured(_request(), _Draft)


async def test_cache_read_is_not_double_charged(tmp_path: Path) -> None:
    usage = {
        "prompt_tokens": 1000,
        "completion_tokens": 0,
        "total_tokens": 1000,
        "prompt_tokens_details": {"cached_tokens": 800},
    }
    client, _ = _client(_replaying(httpx2.Response(200, json=_completion_response(usage=usage)), []))
    response = await client.complete_structured(_request(), _Draft)
    assert response.usage == TokenUsage(200, 0, 800, 0)
    tracker = UsageTracker(part_id="p", document_id="d")
    assert response.usage is not None
    tracker.add(purpose="main_pass", model="anthropic/claude-sonnet-5.5", usage=response.usage)
    assert tracker.summary().cost_usd == 0.00048
    source = tmp_path / "summary.jsonl"
    source.write_text(json.dumps({"event": "part.summary", **tracker.summary().to_dict()}), encoding="utf-8")
    rows, skipped = read_summaries(source)
    report = write_report(rows, tmp_path / "report.csv", skipped)
    assert report["cache_share"] == 0.8
    assert report["cost_median"] == 0.00048


async def test_structured_request_body_uses_strict_json_schema() -> None:
    captured: list[httpx2.Request] = []
    client, _ = _client(_replaying(httpx2.Response(200, json=_completion_response()), captured))

    await client.complete_structured(_request(system=(SystemBlock("shared context"),)), _Draft)

    body = json.loads(captured[0].content)
    assert body["response_format"]["type"] == "json_schema"
    json_schema = body["response_format"]["json_schema"]
    assert json_schema["name"] == "_Draft"
    assert json_schema["strict"] is True
    # OpenAI's strict mode: no extra properties, every field required.
    assert json_schema["schema"]["additionalProperties"] is False
    assert json_schema["schema"]["required"] == ["title"]
    assert json_schema["schema"]["properties"]["title"]["type"] == "string"
    # System blocks go first, user messages after them.
    assert body["messages"][0] == {"role": "system", "content": "shared context"}
    assert body["messages"][1]["role"] == "user"
    assert body["max_tokens"] == 4096
    assert body["temperature"] == 0.0


async def test_structured_request_body_maps_image_parts() -> None:
    captured: list[httpx2.Request] = []
    client, _ = _client(_replaying(httpx2.Response(200, json=_completion_response()), captured))
    content: tuple[TextPart | ImagePart, ...] = (
        ImagePart(media_type="image/png", data_base64="QUJD"),
        TextPart(text="describe this"),
    )

    await client.complete_structured(_request(messages=(LLMMessage(role="user", content=content),)), _Draft)

    body = json.loads(captured[0].content)
    parts = body["messages"][0]["content"]
    assert parts[0] == {
        "type": "image_url",
        "image_url": {"url": "data:image/png;base64,QUJD"},
    }
    assert parts[1] == {"type": "text", "text": "describe this"}


async def test_structured_broken_json_raises_schema_error() -> None:
    captured: list[httpx2.Request] = []
    client, _ = _client(_replaying(httpx2.Response(200, json=_completion_response(content="not json")), captured))

    with pytest.raises(LLMSchemaError):
        await client.complete_structured(_request(), _Draft)


async def test_structured_empty_content_raises_schema_error() -> None:
    captured: list[httpx2.Request] = []
    client, _ = _client(_replaying(httpx2.Response(200, json=_completion_response(content="")), captured))

    with pytest.raises(LLMSchemaError):
        await client.complete_structured(_request(), _Draft)


async def test_structured_rate_limit_is_mapped() -> None:
    captured: list[httpx2.Request] = []
    rate_limit_body = {"error": {"message": "slow down", "type": "rate_limit_error", "code": None}}
    client, _ = _client(_replaying(httpx2.Response(429, json=rate_limit_body), captured))

    with pytest.raises(LLMRateLimitError):
        await client.complete_structured(_request(), _Draft)


async def test_structured_500_is_mapped_to_generation_error() -> None:
    captured: list[httpx2.Request] = []
    client, _ = _client(_replaying(httpx2.Response(500, json=_ERROR_BODY), captured))

    with pytest.raises(LLMGenerationError):
        await client.complete_structured(_request(), _Draft)


async def test_structured_timeout_is_mapped() -> None:
    # The SDK maps httpx.TimeoutException to openai.APITimeoutError; the
    # client must turn it into LLMTimeoutError (own outcome "timeout"), not
    # the generic generation_error.
    def timing_out(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ReadTimeout("timed out")

    client, _ = _client(timing_out)

    with pytest.raises(LLMTimeoutError):
        await client.complete_structured(_request(), _Draft)


async def test_structured_length_cut_raises_truncated_error() -> None:
    # Same stop semantics as ClaudeClient: finish_reason=length is a
    # deterministic truncation, not a schema error (a retry with the same
    # max_tokens would fail the same way).
    captured: list[httpx2.Request] = []
    body = _completion_response(content='{"title": "unclosed', finish_reason="length")
    client, _ = _client(_replaying(httpx2.Response(200, json=body), captured))

    with pytest.raises(LLMOutputTruncatedError, match="length"):
        await client.complete_structured(_request(), _Draft)


async def test_structured_refusal_raises_generation_error() -> None:
    captured: list[httpx2.Request] = []
    body = _completion_response(content=None)
    body["choices"][0]["message"]["refusal"] = "I cannot help with that."
    client, _ = _client(_replaying(httpx2.Response(200, json=body), captured))

    with pytest.raises(LLMGenerationError):
        await client.complete_structured(_request(), _Draft)


async def test_plain_complete_returns_usage_mapping() -> None:
    captured: list[httpx2.Request] = []
    usage = {"prompt_tokens": 3, "completion_tokens": 5, "total_tokens": 8}
    http_client = httpx2.AsyncClient(
        transport=httpx2.MockTransport(
            _replaying(httpx2.Response(200, json=_completion_response(content="hello", usage=usage)), captured)
        )
    )
    plain_client = OpenAICompatibleLLMClient(
        settings=_settings(),
        client=AsyncOpenAI(api_key="test-key", base_url=_BASE_URL, max_retries=0, http_client=http_client),
    )

    response = await plain_client.complete((LLMMessage(role="user", content="hi"),))

    assert response.content == "hello"
    assert response.model == "llama3.2"
    assert response.finish_reason == "stop"
    # This reply has no prompt_tokens_details, so cache_read is 0.
    assert response.usage == TokenUsage(
        input_tokens=3,
        output_tokens=5,
        cache_read_input_tokens=0,
        cache_creation_input_tokens=0,
    )
    assert response.metadata == {"id": "chatcmpl-1", "created": 1700000000}
    body = json.loads(captured[0].content)
    # Plain complete sends no sampling knobs: provider defaults apply.
    assert "temperature" not in body
    assert "max_tokens" not in body


async def test_ping_true_on_200() -> None:
    client, _ = _client(_replaying(httpx2.Response(200, json={"data": []}), []))

    assert await client.ping() is True


async def test_ping_false_on_500() -> None:
    client, _ = _client(_replaying(httpx2.Response(500, json=_ERROR_BODY), []))

    assert await client.ping() is False


async def test_close_closes_the_sdk_http_client() -> None:
    client, http_client = _client(_replaying(httpx2.Response(200, json=_completion_response()), []))

    await client.close()

    assert http_client.is_closed
