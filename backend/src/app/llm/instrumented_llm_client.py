"""Instrumented decorator client: records metrics and logs over any LLMClient.

Ported from faq-assistant and taught two Grasp-specific things: the purpose
tag (every resolver request has a step name) and the four usage counters
from TokenUsage (input / output / cache read / cache creation).

Metrics with the ``llm.complete`` prefix: duration_seconds (histogram,
buckets 1..180), requests (counter), usage.* (histogram — per-call token
distribution). Tags: model, provider, outcome (success | invalid_input |
schema_error | rate_limit_error | generation_error | unexpected_error) and
purpose for structured calls. One INFO log line per call.
"""

from collections.abc import Mapping, Sequence
from logging import Logger
from time import perf_counter

from pydantic import BaseModel

from src.app.contracts.llm.llm_message import LLMMessage
from src.app.contracts.llm.llm_request import LLMRequest
from src.app.contracts.llm.llm_response import LLMResponse
from src.app.contracts.llm.structured_response import StructuredResponse, TokenUsage
from src.app.exceptions.llm import LLMGenerationError, LLMInputError, LLMRateLimitError, LLMSchemaError
from src.app.interfaces.llm.llm_client import LLMClient
from src.app.interfaces.observability.metrics_collector import MetricsCollector, MetricTags

_LLM_DURATION_BUCKETS = (1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 60.0, 90.0, 120.0, 180.0)
_TOKENS_BUCKETS = (100.0, 250.0, 500.0, 1000.0, 2500.0, 5000.0, 10000.0, 25000.0, 50000.0)

_USAGE_FIELDS = (
    "input_tokens",
    "output_tokens",
    "cache_read_input_tokens",
    "cache_creation_input_tokens",
)

_PLAIN_USAGE_FIELDS = ("prompt_tokens", "completion_tokens", "total_tokens")

_UNSET_PURPOSE = "unspecified"

_METRIC_PREFIX = "llm.complete"


class InstrumentedLLMClient(LLMClient):
    def __init__(
        self,
        *,
        client: LLMClient,
        logger: Logger,
        metrics: MetricsCollector,
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
        except LLMInputError:
            duration = self._observe_failure(started_at=started_at, outcome="invalid_input")
            self._logger.warning(
                "LLM input is invalid: model=%s provider=%s in %.3fs.",
                self.model_name, self.provider_name, duration, exc_info=True,
            )
            raise
        except LLMRateLimitError:
            duration = self._observe_failure(started_at=started_at, outcome="rate_limit_error")
            self._logger.warning(
                "LLM rate limit: model=%s provider=%s in %.3fs.",
                self.model_name, self.provider_name, duration, exc_info=True,
            )
            raise
        except LLMGenerationError:
            duration = self._observe_failure(started_at=started_at, outcome="generation_error")
            self._logger.error(
                "LLM generation failed: model=%s provider=%s in %.3fs.",
                self.model_name, self.provider_name, duration, exc_info=True,
            )
            raise
        except Exception:
            duration = self._observe_failure(started_at=started_at, outcome="unexpected_error")
            self._logger.exception(
                "Unexpected LLM client error: model=%s provider=%s in %.3fs.",
                self.model_name, self.provider_name, duration,
            )
            raise

        duration = self._observe_duration(started_at=started_at, outcome="success", purpose=_UNSET_PURPOSE)
        self._record_request(outcome="success", purpose=_UNSET_PURPOSE)
        self._record_plain_usage(response)
        self._logger.info(
            "LLM complete: purpose=%s model=%s in %.3fs usage=%s",
            _UNSET_PURPOSE, self.model_name, duration, response.usage or {},
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
        except LLMInputError:
            duration = self._observe_failure(started_at=started_at, outcome="invalid_input", purpose=request.purpose)
            self._logger.warning(
                "LLM input is invalid: purpose=%s model=%s in %.3fs.",
                request.purpose, self.model_name, duration, exc_info=True,
            )
            raise
        except LLMSchemaError as exc:
            duration = self._observe_failure(started_at=started_at, outcome="schema_error", purpose=request.purpose)
            self._logger.warning(
                "LLM schema mismatch: purpose=%s model=%s in %.3fs error=%s.",
                request.purpose, self.model_name, duration, exc, exc_info=True,
            )
            raise
        except LLMRateLimitError:
            duration = self._observe_failure(started_at=started_at, outcome="rate_limit_error", purpose=request.purpose)
            self._logger.warning(
                "LLM rate limit: purpose=%s model=%s in %.3fs.",
                request.purpose, self.model_name, duration, exc_info=True,
            )
            raise
        except LLMGenerationError:
            duration = self._observe_failure(started_at=started_at, outcome="generation_error", purpose=request.purpose)
            self._logger.error(
                "LLM generation failed: purpose=%s model=%s in %.3fs.",
                request.purpose, self.model_name, duration, exc_info=True,
            )
            raise
        except Exception:
            duration = self._observe_failure(started_at=started_at, outcome="unexpected_error", purpose=request.purpose)
            self._logger.exception(
                "Unexpected LLM client error: purpose=%s model=%s in %.3fs.",
                request.purpose, self.model_name, duration,
            )
            raise

        duration = self._observe_duration(started_at=started_at, outcome="success", purpose=request.purpose)
        self._record_request(outcome="success", purpose=request.purpose)
        self._record_usage(response.usage, purpose=request.purpose)
        self._logger.info(
            "LLM structured: purpose=%s model=%s in %.3fs in_tokens=%s out_tokens=%s "
            "cache_read_tokens=%s cache_creation_tokens=%s",
            request.purpose,
            self.model_name,
            duration,
            response.usage.input_tokens if response.usage else "-",
            response.usage.output_tokens if response.usage else "-",
            response.usage.cache_read_input_tokens if response.usage else "-",
            response.usage.cache_creation_input_tokens if response.usage else "-",
        )
        return response

    async def ping(self) -> bool:
        return await self._client.ping()

    async def close(self) -> None:
        close = getattr(self._client, "close", None)
        if callable(close):
            await close()

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

    def _observe_failure(
        self,
        *,
        started_at: float,
        outcome: str,
        purpose: str = _UNSET_PURPOSE,
    ) -> float:
        duration = self._observe_duration(started_at=started_at, outcome=outcome, purpose=purpose)
        self._record_request(outcome=outcome, purpose=purpose)
        return duration

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
        if not response.usage:
            return
        mapped = self._token_usage_from_mapping(response.usage)
        if mapped is None:
            return
        self._record_usage(mapped)

    @staticmethod
    def _token_usage_from_mapping(usage: object) -> TokenUsage | None:
        if not isinstance(usage, Mapping):
            return None
        values: dict[str, int] = {}
        for field in _PLAIN_USAGE_FIELDS:
            raw = usage.get(field, 0)
            values[field] = int(raw) if isinstance(raw, (int, float)) else 0
        if not any(values.values()):
            return None
        return TokenUsage(
            input_tokens=values["prompt_tokens"],
            output_tokens=values["completion_tokens"],
            cache_read_input_tokens=0,
            cache_creation_input_tokens=0,
        )
