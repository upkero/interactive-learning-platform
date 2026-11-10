"""Live tests against the real Anthropic API (2.1 acceptance criteria).

They cost real money and need a real key, so they are excluded from the
default run (``addopts = "-m 'not live'"``) and skipped unless
``LLM_API_KEY`` is set. Run them explicitly with the full profile:

    LLM_PROVIDER=anthropic LLM_MODEL=claude-sonnet-5-5 LLM_API_KEY=sk-ant-... \
        uv run pytest -m live -v

Via OpenRouter (its /api/v1/messages endpoint is Anthropic-compatible):

    LLM_PROVIDER=anthropic LLM_MODEL=anthropic/claude-sonnet-5.5 \
        LLM_API_KEY=sk-or-... LLM_BASE_URL=https://openrouter.ai/api \
        uv run pytest -m live -v

Covered criteria:
- 2.1.1 structured output: ``call_structured`` returns a validated PageDraft
  from the real model;
- 2.1.4 prompt caching: two calls with the same ``SystemBlock(cache=True)``
  longer than the cacheable minimum — the first reports
  ``cache_creation_input_tokens > 0``, the second
  ``cache_read_input_tokens > 0``.
"""

import os

import pytest
from pydantic import BaseModel

from src.app.contracts.llm.llm_message import LLMMessage
from src.app.contracts.llm.llm_request import LLMRequest
from src.app.contracts.llm.system_block import SystemBlock
from src.app.core.settings.llm import LLMSettings
from src.app.llm.claude_client import ClaudeClient
from src.app.llm.factory import create_llm_client
from src.app.llm.structured import call_structured

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        not os.environ.get("LLM_API_KEY"),
        reason="live test needs LLM_API_KEY",
    ),
]


class PageDraft(BaseModel):
    title: str
    summary: str


def _client() -> ClaudeClient:
    settings = LLMSettings(_env_file=None)
    assert settings.provider == "anthropic", "live tests target the Anthropic profile"
    client = create_llm_client(settings)
    assert isinstance(client, ClaudeClient)
    return client


def _cached_context() -> SystemBlock:
    """A system block comfortably above the 512-token cacheable minimum."""
    return SystemBlock(
        "You are a careful technical writer. " * 40,
        cache=True,
    )


async def test_call_structured_returns_page_draft() -> None:
    client = _client()
    request = LLMRequest(
        purpose="main_pass",
        system=(_cached_context(),),
        messages=(LLMMessage(role="user", content="Draft a page about photosynthesis: title and summary."),),
    )

    draft = await call_structured(client, request, PageDraft)

    assert isinstance(draft, PageDraft)
    assert draft.title.strip()
    assert draft.summary.strip()


async def test_prompt_caching_fires_on_second_call() -> None:
    client = _client()
    request = LLMRequest(
        purpose="main_pass",
        system=(_cached_context(),),
        messages=(LLMMessage(role="user", content="Reply with the single word: ready."),),
    )

    first = await client.complete_structured(request, PageDraft)
    second = await client.complete_structured(request, PageDraft)

    # The cacheable prefix sits close to the 512-token minimum, so make sure
    # the first call actually created the cache entry.
    assert first.usage is not None
    assert first.usage.cache_creation_input_tokens > 0
    assert second.usage is not None
    assert second.usage.cache_read_input_tokens > 0
