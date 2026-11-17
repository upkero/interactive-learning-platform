"""InstrumentedLLMClient unit tests on RecordingMetricsCollector (all outcome branches)."""

from logging import getLogger

import pytest
from pydantic import BaseModel

from src.app.contracts.llm.llm_message import LLMMessage
from src.app.contracts.llm.llm_request import LLMPurpose, LLMRequest
from src.app.contracts.llm.llm_response import LLMResponse
from src.app.contracts.llm.system_block import SystemBlock
from src.app.contracts.llm.token_usage import TokenUsage
from src.app.exceptions.llm import (
    LLMGenerationError,
    LLMInputError,
    LLMOutputTruncatedError,
    LLMRateLimitError,
    LLMSchemaError,
    LLMTimeoutError,
)
from src.app.llm.instrumented_llm_client import InstrumentedLLMClient
from tests.support.fakes.llm.llm_client import FakeLLMClient
from tests.support.fakes.observability.metrics_collector import RecordingMetricsCollector

pytestmark = pytest.mark.unit


class _Draft(BaseModel):
    title: str = "x"


def _tags(outcome: str, purpose: str = "unspecified") -> dict[str, str]:
    return {"model": "fake-model", "provider": "fake", "outcome": outcome, "purpose": purpose}


def _counter_labels(metrics: RecordingMetricsCollector, outcome: str, purpose: str = "unspecified") -> bool:
    """Every llm.complete.requests counter carries exactly these labels."""
    counters = metrics.counters_named("llm.complete.requests")
    return bool(counters) and all(counter.labels == _tags(outcome, purpose) for counter in counters)


def _instrumented(fake: FakeLLMClient, metrics: RecordingMetricsCollector) -> InstrumentedLLMClient:
    return InstrumentedLLMClient(client=fake, logger=getLogger("test.grasp.llm"), metrics=metrics)


def _request(purpose: LLMPurpose = "main_pass", *, system: tuple[SystemBlock, ...] = ()) -> LLMRequest:
    return LLMRequest(
        purpose=purpose,
        messages=(LLMMessage(role="user", content="go"),),
        system=system,
    )


async def test_structured_success_records_all_metrics(caplog: pytest.LogCaptureFixture) -> None:
    fake = FakeLLMClient(structured=[_Draft()], usage=TokenUsage(10, 5, 2, 1))
    metrics = RecordingMetricsCollector()
    caplog.set_level("INFO")

    instrumented = _instrumented(fake, metrics)
    response = await instrumented.complete_structured(_request(), _Draft)

    assert response.value == _Draft()

    request_counters = metrics.counters_named("llm.complete.requests")
    assert len(request_counters) == 1
    assert request_counters[0].labels == _tags("success", "main_pass")
    assert request_counters[0].by == 1

    durations = metrics.histograms_named("llm.complete.duration_seconds")
    assert len(durations) == 1

    usage_names = (
        "llm.complete.usage.input_tokens",
        "llm.complete.usage.output_tokens",
        "llm.complete.usage.cache_read_input_tokens",
        "llm.complete.usage.cache_creation_input_tokens",
    )
    for name, value in zip(usage_names, (10.0, 5.0, 2.0, 1.0), strict=True):
        records = metrics.histograms_named(name)
        assert any(record.value == value for record in records), f"missing usage histogram {name}"

    assert "LLM call completed." in caplog.text
    record = caplog.records[-1]
    assert record.__dict__["purpose"] == "main_pass"
    assert record.__dict__["input_tokens"] == 10
    assert record.__dict__["cache_read_input_tokens"] == 2


async def test_structured_schema_error_maps_outcome(caplog: pytest.LogCaptureFixture) -> None:
    fake = FakeLLMClient(structured=[LLMSchemaError("bad json")])
    metrics = RecordingMetricsCollector()
    instrumented = _instrumented(fake, metrics)

    with pytest.raises(LLMSchemaError):
        await instrumented.complete_structured(_request("quiz_gen"), _Draft)

    durations = metrics.histograms_named("llm.complete.duration_seconds")
    assert durations
    assert _counter_labels(metrics, "schema_error", "quiz_gen")
    assert "LLM call failed." in caplog.text
    assert caplog.records[-1].__dict__["outcome"] == "schema_error"
    assert caplog.records[-1].__dict__["purpose"] == "quiz_gen"
    # Routine schema failures must not spam the log with tracebacks.
    assert "ValidationError" not in caplog.text
    assert not metrics.histograms_named("llm.complete.usage.input_tokens")


async def test_structured_rate_limit_maps_outcome() -> None:
    fake = FakeLLMClient(structured=[LLMRateLimitError()])
    metrics = RecordingMetricsCollector()
    instrumented = _instrumented(fake, metrics)

    with pytest.raises(LLMRateLimitError):
        await instrumented.complete_structured(_request("judge"), _Draft)

    assert _counter_labels(metrics, "rate_limit_error", "judge")


async def test_structured_timeout_maps_outcome() -> None:
    fake = FakeLLMClient(structured=[LLMTimeoutError("provider timed out")])
    metrics = RecordingMetricsCollector()
    instrumented = _instrumented(fake, metrics)

    with pytest.raises(LLMTimeoutError):
        await instrumented.complete_structured(_request("judge"), _Draft)

    assert _counter_labels(metrics, "timeout", "judge")


async def test_structured_generation_error_maps_outcome() -> None:
    fake = FakeLLMClient(structured=[LLMGenerationError("sdk boom")])
    metrics = RecordingMetricsCollector()
    instrumented = _instrumented(fake, metrics)

    with pytest.raises(LLMGenerationError):
        await instrumented.complete_structured(_request("codegen"), _Draft)

    assert _counter_labels(metrics, "generation_error", "codegen")


async def test_structured_unexpected_error_maps_outcome() -> None:
    fake = FakeLLMClient(structured=[RuntimeError("surprise")])
    metrics = RecordingMetricsCollector()
    instrumented = _instrumented(fake, metrics)

    with pytest.raises(RuntimeError):
        await instrumented.complete_structured(_request("vision"), _Draft)

    assert _counter_labels(metrics, "unexpected_error", "vision")


async def test_structured_truncated_error_gets_its_own_outcome() -> None:
    # Truncated output is a subclass of LLMGenerationError but must NOT be
    # counted as generation_error: it would hide the "raise max_tokens"
    # signal behind generic failures.
    fake = FakeLLMClient(structured=[LLMOutputTruncatedError("cut off")])
    metrics = RecordingMetricsCollector()
    instrumented = _instrumented(fake, metrics)

    with pytest.raises(LLMOutputTruncatedError):
        await instrumented.complete_structured(_request("main_pass"), _Draft)

    assert _counter_labels(metrics, "output_truncated", "main_pass")


async def test_plain_complete_success_and_invalid_input() -> None:
    ok = FakeLLMClient(completions=[LLMResponse(content="hello", usage=TokenUsage(input_tokens=3, output_tokens=5))])
    metrics = RecordingMetricsCollector()
    instrumented = _instrumented(ok, metrics)

    response = await instrumented.complete((LLMMessage(role="user", content="q"),))
    assert response.content == "hello"
    assert _counter_labels(metrics, "success")
    input_records = metrics.histograms_named("llm.complete.usage.input_tokens")
    assert input_records and input_records[0].value == 3.0
    output_records = metrics.histograms_named("llm.complete.usage.output_tokens")
    assert output_records and output_records[0].value == 5.0

    bad = FakeLLMClient(completions=[LLMInputError("empty")])
    metrics2 = RecordingMetricsCollector()
    instrumented2 = _instrumented(bad, metrics2)
    with pytest.raises(LLMInputError):
        await instrumented2.complete((LLMMessage(role="user", content="q"),))
    assert metrics2.histograms_named("llm.complete.duration_seconds")
    assert _counter_labels(metrics2, "invalid_input")


async def test_plain_complete_error_branches() -> None:
    for exception, outcome in (
        (LLMRateLimitError(), "rate_limit_error"),
        (LLMTimeoutError("slow"), "timeout"),
        (LLMGenerationError("boom"), "generation_error"),
        (RuntimeError("surprise"), "unexpected_error"),
    ):
        fake = FakeLLMClient(completions=[exception])
        metrics = RecordingMetricsCollector()
        instrumented = _instrumented(fake, metrics)

        with pytest.raises(type(exception)):
            await instrumented.complete((LLMMessage(role="user", content="q"),))

        assert metrics.histograms_named("llm.complete.duration_seconds")
        assert _counter_labels(metrics, outcome)


async def test_structured_without_usage_records_no_usage_metrics() -> None:
    fake = FakeLLMClient(structured=[_Draft()])
    metrics = RecordingMetricsCollector()
    instrumented = _instrumented(fake, metrics)

    response = await instrumented.complete_structured(_request(), _Draft)

    assert response.usage is None
    assert not metrics.histograms_named("llm.complete.usage.input_tokens")
    assert len(metrics.counters_named("llm.complete.requests")) == 1


async def test_missing_usage_records_nothing() -> None:
    fake = FakeLLMClient(completions=[LLMResponse(content="x", usage=None)])
    metrics = RecordingMetricsCollector()
    instrumented = _instrumented(fake, metrics)

    await instrumented.complete((LLMMessage(role="user", content="q"),))

    assert not metrics.histograms_named("llm.complete.usage.input_tokens")


async def test_ping_and_close_are_pass_through() -> None:
    fake = FakeLLMClient()
    instrumented = _instrumented(fake, RecordingMetricsCollector())

    assert await instrumented.ping() is True
    assert fake.pinged is True
    await instrumented.close()
    assert fake.closed is True


async def test_cache_true_call_without_cache_tokens_logs_debug(caplog: pytest.LogCaptureFixture) -> None:
    fake = FakeLLMClient(structured=[_Draft()], usage=TokenUsage(10, 5, 0, 0))
    instrumented = _instrumented(fake, RecordingMetricsCollector())
    caplog.set_level("DEBUG")

    await instrumented.complete_structured(_request(system=(SystemBlock("short context", cache=True),)), _Draft)

    assert "LLM prompt cache miss" in caplog.text
    record = caplog.records[-1]
    assert record.__dict__["purpose"] == "main_pass"


async def test_cache_hit_does_not_log_cache_miss(caplog: pytest.LogCaptureFixture) -> None:
    fake = FakeLLMClient(structured=[_Draft()], usage=TokenUsage(10, 5, 8, 0))
    instrumented = _instrumented(fake, RecordingMetricsCollector())
    caplog.set_level("DEBUG")

    await instrumented.complete_structured(_request(system=(SystemBlock("long context", cache=True),)), _Draft)

    assert "cache miss" not in caplog.text


async def test_success_log_carries_structured_fields(caplog: pytest.LogCaptureFixture) -> None:
    """Rule 1.8: constant message text, data goes to extra fields."""
    fake = FakeLLMClient(structured=[_Draft()], usage=TokenUsage(10, 5, 2, 1))
    instrumented = _instrumented(fake, RecordingMetricsCollector())
    caplog.set_level("INFO", logger="test.grasp.llm")

    await instrumented.complete_structured(_request(), _Draft)

    record = caplog.records[-1]
    assert record.message == "LLM call completed."
    assert record.__dict__["purpose"] == "main_pass"
    assert record.__dict__["model"] == "fake-model"
    assert record.__dict__["outcome"] == "success"
    assert isinstance(record.__dict__["duration_s"], float)
    assert record.__dict__["input_tokens"] == 10
    assert record.__dict__["output_tokens"] == 5
    assert record.__dict__["cache_read_input_tokens"] == 2
    assert record.__dict__["cache_creation_input_tokens"] == 1


async def test_failure_log_carries_structured_fields(caplog: pytest.LogCaptureFixture) -> None:
    fake = FakeLLMClient(structured=[LLMSchemaError("bad shape")])
    instrumented = _instrumented(fake, RecordingMetricsCollector())
    caplog.set_level("WARNING", logger="test.grasp.llm")

    with pytest.raises(LLMSchemaError):
        await instrumented.complete_structured(_request(), _Draft)

    record = caplog.records[-1]
    assert record.message == "LLM call failed."
    assert record.__dict__["outcome"] == "schema_error"
    assert record.__dict__["purpose"] == "main_pass"
    assert isinstance(record.__dict__["duration_s"], float)


async def test_without_metrics_calls_still_log(caplog: pytest.LogCaptureFixture) -> None:
    """No collector wired: no metric calls, the INFO line is always written."""
    fake = FakeLLMClient(structured=[_Draft()], usage=TokenUsage(10, 5, 0, 0))
    instrumented = InstrumentedLLMClient(client=fake, logger=getLogger("test.grasp.llm"))
    caplog.set_level("INFO", logger="test.grasp.llm")

    response = await instrumented.complete_structured(_request(), _Draft)

    assert response.value.title == "x"
    assert "LLM call completed." in caplog.text
