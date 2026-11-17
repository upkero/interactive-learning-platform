"""Instrumented decorator client: records metrics and logs over any LLMClient.

Ported from faq-assistant and taught two Grasp-specific things: the purpose
tag (every resolver request has a step name) and the four usage counters
from TokenUsage (input / output / cache read / cache creation).

Metrics with the ``llm.complete`` prefix: requests (counter, labels
model/provider/outcome/purpose) and duration/usage histograms (unlabeled —
the 1.8 MetricsCollector facade keeps histograms label-free; outcome and
purpose live in the structured log line). One INFO log line per call.

Expected errors are mapped to log level and outcome via a single table
(``_ERROR_HANDLERS``); every failure is one log line without a traceback —
the provider error text goes into the ``error`` field (5xx handlers log
the traceback themselves).

Metrics are optional: with ``metrics=None`` no metric is written and the
logs are always emitted. Implementations arrive with story 1.8.1.
"""

from collections.abc import Mapping, Sequence
from logging import ERROR, WARNING, Logger
from time import perf_counter
from typing import NoReturn

from pydantic import BaseModel

from src.app.contracts.llm.llm_message import LLMMessage
from src.app.contracts.llm.llm_request import LLMRequest
from src.app.contracts.llm.llm_response import LLMResponse
from src.app.contracts.llm.structured_response import StructuredResponse
from src.app.contracts.llm.token_usage import TokenUsage
from src.app.exceptions.llm import (
    LLMGenerationError,
    LLMInputError,
    LLMOutputTruncatedError,
    LLMRateLimitError,
    LLMSchemaError,
    LLMTimeoutError,
)
from src.app.interfaces.llm.llm_client import LLMClient
from src.app.interfaces.observability.metrics_collector import MetricsCollector

_USAGE_FIELDS = (
    "input_tokens",
    "output_tokens",
    "cache_read_input_tokens",
    "cache_creation_input_tokens",
)

_UNSET_PURPOSE = "unspecified"

_METRIC_PREFIX = "llm.complete"

# Exception type -> (outcome tag, log level). Order matters: Exception is
# the catch-all for unexpected errors, LLMTimeoutError must precede
# LLMGenerationError (it is a subclass).
_ERROR_HANDLERS: tuple[tuple[type[BaseException], str, int], ...] = (
    (LLMInputError, "invalid_input", WARNING),
    (LLMSchemaError, "schema_error", WARNING),
    (LLMRateLimitError, "rate_limit_error", WARNING),
    (LLMOutputTruncatedError, "output_truncated", WARNING),
    (LLMTimeoutError, "timeout", WARNING),
    (LLMGenerationError, "generation_error", ERROR),
    (Exception, "unexpected_error", ERROR),
)


def _usage_log_fields(usage: TokenUsage | None) -> dict[str, int | None]:
    """Token counters as structured log fields (None when usage is absent)."""
    if usage is None:
        return dict.fromkeys(_USAGE_FIELDS)
    return {field: getattr(usage, field) for field in _USAGE_FIELDS}


class InstrumentedLLMClient(LLMClient):
    def __init__(
        self,
        *,
        client: LLMClient,
        logger: Logger,
        metrics: MetricsCollector | None = None,
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
        self._record_usage(response.usage)
        self._logger.info(
            "LLM call completed.",
            extra={
                "purpose": _UNSET_PURPOSE,
                "model": self.model_name,
                "outcome": "success",
                "duration_s": round(duration, 3),
                **_usage_log_fields(response.usage),
            },
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
            "LLM call completed.",
            extra={
                "purpose": request.purpose,
                "model": self.model_name,
                "outcome": "success",
                "duration_s": round(duration, 3),
                **_usage_log_fields(usage),
            },
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
        for exc_type, outcome, level in _ERROR_HANDLERS:
            if isinstance(exc, exc_type):
                duration = self._observe_duration(started_at=started_at, outcome=outcome, purpose=purpose)
                self._record_request(outcome=outcome, purpose=purpose)
                self._logger.log(
                    level,
                    "LLM call failed.",
                    extra={
                        "outcome": outcome,
                        "purpose": purpose,
                        "model": self.model_name,
                        "duration_s": round(duration, 3),
                        "error": str(exc),
                    },
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
                "LLM prompt cache miss: cached block is likely below the provider minimum.",
                extra={"purpose": request.purpose, "model": self.model_name},
            )

    def _metric_tags(self, *, outcome: str, purpose: str) -> Mapping[str, str]:
        return {
            "model": self.model_name,
            "provider": self.provider_name,
            "outcome": outcome,
            "purpose": purpose,
        }

    def _record_request(self, *, outcome: str, purpose: str) -> None:
        if self._metrics is None:
            return
        self._metrics.increment_counter(
            f"{_METRIC_PREFIX}.requests",
            labels=self._metric_tags(outcome=outcome, purpose=purpose),
        )

    def _observe_duration(self, *, started_at: float, outcome: str, purpose: str) -> float:
        duration_seconds = perf_counter() - started_at
        if self._metrics is not None:
            # The 1.8 facade keeps histograms label-free: outcome/purpose go
            # to the counter above and the structured log line.
            self._metrics.observe_histogram(f"{_METRIC_PREFIX}.duration_seconds", duration_seconds)
        return duration_seconds

    def _record_usage(self, usage: TokenUsage | None, *, purpose: str = _UNSET_PURPOSE) -> None:
        if self._metrics is None or usage is None:
            return
        for field in _USAGE_FIELDS:
            self._metrics.observe_histogram(f"{_METRIC_PREFIX}.usage.{field}", float(getattr(usage, field)))
