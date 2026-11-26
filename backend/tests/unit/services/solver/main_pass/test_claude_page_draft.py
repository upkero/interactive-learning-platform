"""Check the main-pass schema through the Anthropic SDK transport."""

import json

import httpx2
import pytest
from anthropic import AsyncAnthropic  # noqa: TID251 - exercise the SDK schema transport
from pydantic import SecretStr

from src.app.contracts.llm.llm_message import LLMMessage
from src.app.contracts.llm.llm_request import LLMRequest
from src.app.core.settings.llm import LLMSettings
from src.app.exceptions.llm import LLMSchemaError
from src.app.llm.claude_client import ClaudeClient
from src.app.services.solver.main_pass.directives import PageDraft
from tests.support.fixtures.main_pass import build_page_draft

pytestmark = pytest.mark.unit


def _client(payload: dict[str, object], captured: list[httpx2.Request]) -> ClaudeClient:
    def respond(request: httpx2.Request) -> httpx2.Response:
        captured.append(request)
        return httpx2.Response(
            200,
            json={
                "id": "msg_1",
                "type": "message",
                "role": "assistant",
                "model": "claude-sonnet-5-5",
                "content": [{"type": "text", "text": json.dumps(payload)}],
                "stop_reason": "end_turn",
                "stop_sequence": None,
                "usage": {"input_tokens": 10, "output_tokens": 5},
            },
        )

    http_client = httpx2.AsyncClient(transport=httpx2.MockTransport(respond))
    sdk = AsyncAnthropic(api_key="test-key", max_retries=0, http_client=http_client)
    settings = LLMSettings(
        provider="anthropic", api_key=SecretStr("test-key"), model="claude-sonnet-5-5", _env_file=None
    )
    return ClaudeClient(settings=settings, client=sdk)


def _request() -> LLMRequest:
    return LLMRequest(purpose="main_pass", messages=(LLMMessage(role="user", content="draft a page"),))


async def test_structured_request_accepts_the_page_draft_schema() -> None:
    captured: list[httpx2.Request] = []
    client = _client(build_page_draft(), captured)
    try:
        result = await client.complete_structured(_request(), PageDraft)
    finally:
        await client.close()

    assert isinstance(result.value, PageDraft)
    schema = json.loads(captured[0].content)["output_config"]["format"]["schema"]
    assert schema["properties"]["markdown"]["type"] == "string"
    assert "directives" in schema["properties"]
    assert '"ref"' in json.dumps(schema)
    assert '"image_id"' in json.dumps(schema)


async def test_structured_page_draft_constraint_violation_is_a_schema_error() -> None:
    captured: list[httpx2.Request] = []
    client = _client(
        {
            "markdown": '::widget{ref="i1"}\n',
            "directives": [{"ref": "i1", "kind": "widget", "intent": "Wrong prefix."}],
            "key_terms": ["term"],
        },
        captured,
    )
    try:
        with pytest.raises(LLMSchemaError):
            await client.complete_structured(_request(), PageDraft)
    finally:
        await client.close()
