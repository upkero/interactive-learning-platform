"""InstrumentedLLMClient unit tests on RecordingMetricsCollector (all outcome branches)."""

from logging import getLogger

import pytest
from pydantic import BaseModel

from src.app.contracts.llm.llm_message import LLMMessage
from src.app.contracts.llm.llm_request import LLMRequest
from src.app.contracts.llm.llm_response import LLMResponse
from src.app.contracts.llm.structured_response import StructuredResponse, TokenUsage
from src.app.exceptions.llm import LLMGenerationError, LLMInputError, LLMRateLimitError, LLMSchemaError
from src.app.llm.instrumented_llm_client import InstrumentedLLMClient
from tests.support.fakes.llm.llm_client import FakeLLMClient
from tests.support.fakes.observability.metrics_collector import RecordingMetricsCollector


class _Draft(BaseModel):
    title: str = "x"


_SUCCESS_TAGS = {"model": "fake-model", "provider": "fake"}


def _instrumented(fake: FakeLLMClient, metrics: RecordingMetricsCollector) -> InstrumentedLLMClient:
    return InstrumentedLLMClient(client=fake, logger=getLogger("test.grasp.llm"), metrics=metrics)


def _request(purpose: str = "main_pass") -> LLMRequest:
    return LLMRequest(purpose=purpose, messages=(LLMMessage(role="user", content="go"),))


def _tags(outcome: str, purpose: str = "unspecified") -> dict[str, str]:
    return {"model": "fake-model", "provider": "fake", "outcome": outcome, "purpose": purpose}


@pytest.mark.unit
async def test_structured_success_records_all_metrics(caplog: pytest.LogCaptureFixture) -> None:
    fake = FakeLLMClient(responses=[StructuredResponse(_Draft(), usage=TokenUsage(10, 5, 2, 1))])
    metrics = RecordingMetricsCollector()
    caplog.set_level("INFO")

    instrumented = _instrumented(fake, metrics)
    response = await instrumented.complete_structured(_request(), _Draft)

    assert response.value == _Draft()

    request_counters = metrics.counters_named("llm.complete.requests")
    assert len(request_counters) == 1
    assert request_counters[0].tags == _tags("success", "main_pass")
    assert request_counters[0].value == 1

    durations = metrics.histograms_named("llm.complete.duration_seconds")
    assert len(durations) == 1
    assert durations[0].tags == _tags("success", "main_pass")
    assert 1.0 in (durations[0].buckets or ())  # бакеты 1..180

    usage_names = (
        "llm.complete.usage.input_tokens",
        "llm.complete.usage.output_tokens",
        "llm.complete.usage.cache_read_input_tokens",
        "llm.complete.usage.cache_creation_input_tokens",
    )
    for name, value in zip(usage_names, (10.0, 5.0, 2.0, 1.0), strict=True):
        records = metrics.histograms_named(name)
        assert any(
            record.value == value and record.tags == _tags("success", "main_pass") for record in records
        ), f"missing usage histogram {name}"

    assert "LLM structured: purpose=main_pass" in caplog.text
    assert "in_tokens=10" in caplog.text
    assert "cache_read_tokens=2" in caplog.text


@pytest.mark.unit
async def test_structured_schema_error_maps_outcome(caplog: pytest.LogCaptureFixture) -> None:
    fake = FakeLLMClient(responses=[LLMSchemaError("bad json")])
    metrics = RecordingMetricsCollector()
    instrumented = _instrumented(fake, metrics)

    with pytest.raises(LLMSchemaError):
        await instrumented.complete_structured(_request("quiz_gen"), _Draft)

    durations = metrics.histograms_named("llm.complete.duration_seconds")
    assert all(record.tags == _tags("schema_error", "quiz_gen") for record in durations)
    request_counters = metrics.counters_named("llm.complete.requests")
    assert all(counter.tags == _tags("schema_error", "quiz_gen") for counter in request_counters)
    assert "LLM schema mismatch: purpose=quiz_gen" in caplog.text
    assert not metrics.histograms_named("llm.complete.usage.input_tokens")


@pytest.mark.unit
async def test_structured_rate_limit_maps_outcome() -> None:
    fake = FakeLLMClient(responses=[LLMRateLimitError()])
    metrics = RecordingMetricsCollector()
    instrumented = _instrumented(fake, metrics)

    with pytest.raises(LLMRateLimitError):
        await instrumented.complete_structured(_request("judge"), _Draft)

    assert all(
        record.tags == _tags("rate_limit_error", "judge")
        for record in metrics.histograms_named("llm.complete.duration_seconds")
    )


@pytest.mark.unit
async def test_structured_generation_error_maps_outcome() -> None:
    fake = FakeLLMClient(responses=[LLMGenerationError("sdk boom")])
    metrics = RecordingMetricsCollector()
    instrumented = _instrumented(fake, metrics)

    with pytest.raises(LLMGenerationError):
        await instrumented.complete_structured(_request("codegen"), _Draft)

    assert all(
        record.tags == _tags("generation_error", "codegen")
        for record in metrics.histograms_named("llm.complete.duration_seconds")
    )


@pytest.mark.unit
async def test_structured_unexpected_error_maps_outcome() -> None:
    fake = FakeLLMClient(responses=[RuntimeError("surprise")])
    metrics = RecordingMetricsCollector()
    instrumented = _instrumented(fake, metrics)

    with pytest.raises(RuntimeError):
        await instrumented.complete_structured(_request("vision"), _Draft)

    assert all(
        record.tags == _tags("unexpected_error", "vision")
        for record in metrics.histograms_named("llm.complete.duration_seconds")
    )


@pytest.mark.unit
async def test_plain_complete_success_and_invalid_input() -> None:
    ok = FakeLLMClient(responses=[LLMResponse(content="hello", usage={"prompt_tokens": 3, "completion_tokens": 5})])
    metrics = RecordingMetricsCollector()
    instrumented = _instrumented(ok, metrics)

    response = await instrumented.complete((LLMMessage(role="user", content="q"),))
    assert response.content == "hello"
    assert all(counter.tags == _tags("success") for counter in metrics.counters_named("llm.complete.requests"))
    input_records = metrics.histograms_named("llm.complete.usage.input_tokens")
    assert input_records and input_records[0].value == 3.0

    bad = FakeLLMClient(responses=[LLMInputError("empty")])
    metrics2 = RecordingMetricsCollector()
    instrumented2 = _instrumented(bad, metrics2)
    with pytest.raises(LLMInputError):
        await instrumented2.complete((LLMMessage(role="user", content="q"),))
    assert all(
        record.tags == _tags("invalid_input")
        for record in metrics2.histograms_named("llm.complete.duration_seconds")
    )


@pytest.mark.unit
async def test_plain_complete_error_branches() -> None:
    for exception, outcome in (
        (LLMRateLimitError(), "rate_limit_error"),
        (LLMGenerationError("boom"), "generation_error"),
        (RuntimeError("surprise"), "unexpected_error"),
    ):
        fake = FakeLLMClient(responses=[exception])
        metrics = RecordingMetricsCollector()
        instrumented = _instrumented(fake, metrics)

        with pytest.raises(type(exception)):
            await instrumented.complete((LLMMessage(role="user", content="q"),))

        assert all(
            record.tags == _tags(outcome)
            for record in metrics.histograms_named("llm.complete.duration_seconds")
        )


@pytest.mark.unit
async def test_structured_without_usage_records_no_usage_metrics() -> None:
    fake = FakeLLMClient(responses=[StructuredResponse(_Draft())])
    metrics = RecordingMetricsCollector()
    instrumented = _instrumented(fake, metrics)

    response = await instrumented.complete_structured(_request(), _Draft)

    assert response.usage is None
    assert not metrics.histograms_named("llm.complete.usage.input_tokens")
    assert len(metrics.counters_named("llm.complete.requests")) == 1


@pytest.mark.unit
async def test_mapping_without_counters_records_nothing() -> None:
    fake = FakeLLMClient(responses=[LLMResponse(content="x", usage={"total_tokens": 0})])
    metrics = RecordingMetricsCollector()
    instrumented = _instrumented(fake, metrics)

    await instrumented.complete((LLMMessage(role="user", content="q"),))

    assert not metrics.histograms_named("llm.complete.usage.total_tokens")


@pytest.mark.unit
async def test_ping_and_close_are_pass_through() -> None:
    fake = FakeLLMClient()
    instrumented = _instrumented(fake, RecordingMetricsCollector())

    assert await instrumented.ping() is True
    assert fake.pinged is True
    await instrumented.close()
    assert fake.closed is True
