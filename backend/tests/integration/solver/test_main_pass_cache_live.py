"""Paid check of prompt cache reuse between two parts of one document.

Run explicitly with an Anthropic model and credentials configured:
    uv run pytest -m live tests/integration/solver/test_main_pass_cache_live.py

The two parts use their normal document outline. This test may incur charges
and requires provider cache support.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import cast

import pytest
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.contracts.llm.llm_message import LLMMessage
from src.app.contracts.llm.llm_request import LLMRequest
from src.app.contracts.llm.llm_response import LLMResponse
from src.app.contracts.llm.structured_response import StructuredResponse
from src.app.contracts.llm.token_usage import TokenUsage
from src.app.core.settings.llm import get_llm_settings
from src.app.core.settings.solver import SolverSettings
from src.app.interfaces.llm.llm_client import LLMClient
from src.app.llm.factory import create_llm_client
from src.app.observability.noop_metrics_collector import NoopMetricsCollector
from src.app.services.solver.main_pass.main_pass import MainPassService
from tests.support.fakes.db.session import FakeSession
from tests.support.fakes.repositories.widgets import FakePrimitiveRepository
from tests.support.fixtures.main_pass import build_input, build_primitives

pytestmark = [pytest.mark.live, pytest.mark.timeout(600)]


@dataclass
class _Call:
    request: LLMRequest
    usage: TokenUsage | None = None


class _UsageRecorder(LLMClient):
    """Record each attempt, including a failed schema attempt, without changing the service."""

    def __init__(self, inner: LLMClient) -> None:
        self.inner = inner
        self.calls: list[_Call] = []

    @property
    def model_name(self) -> str:
        return self.inner.model_name

    @property
    def provider_name(self) -> str:
        return self.inner.provider_name

    async def complete(self, messages: Sequence[LLMMessage]) -> LLMResponse:
        return await self.inner.complete(messages)

    async def complete_structured[T: BaseModel](self, request: LLMRequest, schema: type[T]) -> StructuredResponse[T]:
        call = _Call(request)
        self.calls.append(call)
        response = await self.inner.complete_structured(request, schema)
        call.usage = response.usage
        return response

    async def ping(self) -> bool:
        return await self.inner.ping()

    async def close(self) -> None:
        await self.inner.close()


async def test_two_parts_reuse_the_document_prefix() -> None:
    settings = get_llm_settings()
    if settings.provider != "anthropic" or settings.api_key is None:
        pytest.skip("Configure LLM_PROVIDER=anthropic and LLM_API_KEY for the paid cache test.")

    repo = FakePrimitiveRepository()
    for primitive in build_primitives():
        await repo.upsert(
            primitive_id=primitive.id,
            version=primitive.version,
            description=primitive.description,
            modes=primitive.modes,
            params_schema=primitive.params_schema,
        )

    first = build_input("neurons")
    second = build_input("activation")
    assert first.document_id == second.document_id
    assert first.part_id != second.part_id

    client = _UsageRecorder(create_llm_client(settings))
    service = MainPassService(
        llm=client,
        session_factory=cast(async_sessionmaker[AsyncSession], lambda: FakeSession()),
        primitives=lambda _: repo,
        settings=SolverSettings(),
        metrics=NoopMetricsCollector(),
    )
    try:
        await service.run(first)
        second_call_index = len(client.calls)
        await service.run(second)
    finally:
        await client.close()

    first_call = client.calls[0]
    second_call = client.calls[second_call_index]
    assert first_call.request.system == second_call.request.system
    assert all(block.cache for block in second_call.request.system)
    assert second_call.usage is not None, "Provider did not return usage for the second part's first request."
    print(f"Second request usage: {second_call.usage}")
    assert second_call.usage.cache_read_input_tokens > 0, (
        f"The second part did not read cached tokens: {second_call.usage}. "
        "Check model support, prefix minimum and provider cache settings."
    )
