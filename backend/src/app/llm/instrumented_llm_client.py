"""Instrumented decorator client: records metrics and logs over any LLMClient.

Ported from faq-assistant and taught two Grasp-specific things: the purpose
tag (every resolver request has a step name) and the four usage counters
from TokenUsage (input / output / cache read / cache creation).

Metrics with the ``llm.complete`` prefix: duration_seconds (histogram,
buckets 1..180), requests (counter), usage.* (histogram — per-call token
distribution). Tags: model, provider, outcome (success | invalid_input |
schema_error | rate_limit_error | generation_error | unexpected_error) and
purpose for structured calls. One INFO log line per call.

Expected errors are mapped to log level and outcome via a single table
(``_ERROR_HANDLERS``): schema and rate-limit failures are routine (one line,
no traceback), input/generation/unexpected failures keep the traceback.
"""

from collections.abc import Sequence
from logging import ERROR, WARNING, Logger
from time import perf_counter
from typing import NoReturn

from pydantic import BaseModel

from src.app.contracts.llm.llm_message import LLMMessage
from src.app.contracts.llm.llm_request import LLMRequest
from src.app.contracts.llm.llm_response import LLMResponse
from src.app.contracts.llm.structured_response import StructuredResponse, TokenUsage
from src.app.exceptions.llm import (
    LLMGenerationError,
    LLMInputError,
    LLMOutputTruncatedError,
    LLMRateLimitError,
    LLMSchemaError,
)
from src.app.interfaces.llm.llm_client import LLMClient
from src.app.interfaces.observability.metrics_collector import MetricsCollectorProtocol, MetricTags

_LLM_DURATION_BUCKETS = (1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 60.0, 90.0, 120.0, 180.0)
_TOKENS_BUCKETS = (100.0, 250.0, 500.0, 1000.0, 2500.0, 5000.0, 10000.0, 25000.0, 50000.0)

_USAGE_FIELDS = (
    "input_tokens",
    "output_tokens",
    "cache_read_input_tokens",
    "cache_creation_input_tokens",
)

_UNSET_PURPOSE = "unspecified"

_METRIC_PREFIX = "llm.complete"

# Exception type -> (outcome tag, log level, keep traceback in the log line).
# Order matters: Exception is the catch-all for unexpected errors.
_ERROR_HANDLERS: tuple[tuple[type[BaseException], str, int, bool], ...] = (
    (LLMInputError, "invalid_input", WARNING, True),
    (LLMSchemaError, "schema_error", WARNING, False),
    (LLMRateLimitError, "rate_limit_error", WARNING, False),
    (LLMOutputTruncatedError, "output_truncated", WARNING, False),
    (LLMGenerationError, "generation_error", ERROR, True),
    (Exception, "unexpected_error", ERROR, True),
)


class InstrumentedLLMClient(LLMClient):
    def __init__(
        self,
        *,
        client: LLMClient,
        logger: Logger,
        metrics: MetricsCollectorProtocol,
    ) -> None:
        self._client = client
        self._logger = logger
        self._metrics = metrics

    @property
    def model_name(self) -> str:
        return self._client.model_name

    @property
    def provider_name(self) -> str:
        return self._client.provider_name

    async def complete(self, messages: Sequence[LLMMessage]) -> LLMResponse:
        started_at = perf_counter()
        try:
            response = await self._client.complete(messages)
        except Exception as exc:
            self._handle_failure(exc, started_at=started_at, purpose=_UNSET_PURPOSE)

        duration = self._observe_duration(started_at=started_at, outcome="success", purpose=_UNSET_PURPOSE)
        self._record_request(outcome="success", purpose=_UNSET_PURPOSE)
        self._record_plain_usage(response)
        self._logger.info(
            "LLM complete: purpose=%s model=%s in %.3fs usage=%s",
            _UNSET_PURPOSE,
            self.model_name,
            duration,
            response.usage or {},
        )
        return response

    async def complete_structured[T: BaseModel](
        self,
        request: LLMRequest,
        schema: type[T],
    ) -> StructuredResponse[T]:
        started_at = perf_counter()
        try:
            response = await self._client.complete_structured(request, schema)
        except Exception as exc:
            self._handle_failure(exc, started_at=started_at, purpose=request.purpose)

        duration = self._observe_duration(started_at=started_at, outcome="success", purpose=request.purpose)
        self._record_request(outcome="success", purpose=request.purpose)
        self._record_usage(response.usage, purpose=request.purpose)
        usage = response.usage
        self._log_cache_miss(request, usage)
        self._logger.info(
            "LLM structured: purpose=%s model=%s in %.3fs in_tokens=%s out_tokens=%s "
            "cache_read_tokens=%s cache_creation_tokens=%s",
            request.purpose,
            self.model_name,
            duration,
            usage.input_tokens if usage else "-",
            usage.output_tokens if usage else "-",
            usage.cache_read_input_tokens if usage else "-",
            usage.cache_creation_input_tokens if usage else "-",
        )
        return response

    async def ping(self) -> bool:
        return await self._client.ping()

    async def close(self) -> None:
        await self._client.close()

    def _handle_failure(
        self,
        exc: BaseException,
        *,
        started_at: float,
        purpose: str,
    ) -> NoReturn:
        """Observe metrics and log the failure; always re-raises ``exc``."""
        for exc_type, outcome, level, with_traceback in _ERROR_HANDLERS:
            if isinstance(exc, exc_type):
                duration = self._observe_duration(started_at=started_at, outcome=outcome, purpose=purpose)
                self._record_request(outcome=outcome, purpose=purpose)
                self._logger.log(
                    level,
                    "LLM call failed: outcome=%s purpose=%s model=%s in %.3fs error=%s.",
                    outcome,
                    purpose,
                    self.model_name,
                    duration,
                    exc,
                    exc_info=exc if with_traceback else None,
                )
                break
        raise exc

    def _log_cache_miss(self, request: LLMRequest, usage: TokenUsage | None) -> None:
        """A cache=True call with zero cache tokens usually means the cached
        block is shorter than the provider minimum (512/4096 tokens)."""
        if (
            usage is not None
            and any(block.cache for block in request.system)
            and usage.cache_read_input_tokens == 0
            and usage.cache_creation_input_tokens == 0
        ):
            self._logger.debug(
                "LLM prompt cache miss: purpose=%s — cached block is likely below the provider minimum.",
                request.purpose,
            )

    def _metric_tags(self, *, outcome: str, purpose: str) -> MetricTags:
        return {
            "model": self.model_name,
            "provider": self.provider_name,
            "outcome": outcome,
            "purpose": purpose,
        }

    def _record_request(self, *, outcome: str, purpose: str) -> None:
        self._metrics.increment_counter(
            f"{_METRIC_PREFIX}.requests",
            tags=self._metric_tags(outcome=outcome, purpose=purpose),
        )

    def _observe_duration(self, *, started_at: float, outcome: str, purpose: str) -> float:
        duration_seconds = perf_counter() - started_at
        self._metrics.observe_histogram(
            f"{_METRIC_PREFIX}.duration_seconds",
            duration_seconds,
            tags=self._metric_tags(outcome=outcome, purpose=purpose),
            buckets=_LLM_DURATION_BUCKETS,
        )
        return duration_seconds

    def _record_usage(self, usage: TokenUsage | None, *, purpose: str = _UNSET_PURPOSE) -> None:
        if usage is None:
            return
        for field in _USAGE_FIELDS:
            self._metrics.observe_histogram(
                f"{_METRIC_PREFIX}.usage.{field}",
                float(getattr(usage, field)),
                tags=self._metric_tags(outcome="success", purpose=purpose),
                buckets=_TOKENS_BUCKETS,
            )

    def _record_plain_usage(self, response: LLMResponse) -> None:
        """Plain completion usage is a mapping with the canonical TokenUsage
        field names (clients normalize provider names before returning)."""
        usage = response.usage
        if not usage or not any(usage.values()):
            return
        self._record_usage(
            TokenUsage(
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
                cache_read_input_tokens=usage.get("cache_read_input_tokens", 0),
                cache_creation_input_tokens=usage.get("cache_creation_input_tokens", 0),
            )
        )
