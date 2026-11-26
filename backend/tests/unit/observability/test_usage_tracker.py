import asyncio
import csv
import json
from pathlib import Path

import pytest

from evals.usage_report import read_summaries, write_report
from src.app.contracts.llm.token_usage import TokenUsage
from src.app.core.settings.pricing import get_model_pricing
from src.app.observability.usage_tracker import UsageTracker, bind_usage_tracker, get_usage_tracker
from tests.support.fakes.observability.metrics_collector import RecordingMetricsCollector

pytestmark = pytest.mark.unit


def test_usage_tracker_accumulates_usage_stages_and_summary(caplog: pytest.LogCaptureFixture) -> None:
    metrics = RecordingMetricsCollector()
    tracker = UsageTracker(part_id="part", document_id="document", metrics=metrics)
    tracker.add(
        purpose="resolver",
        model="llama3.2",
        usage=TokenUsage(input_tokens=10, output_tokens=4, cache_read_input_tokens=2),
    )
    with tracker.stage("resolving"):
        pass
    summary = tracker.summary()
    assert summary.part_id == "part"
    assert summary.usage == {"resolver": {"input": 10, "output": 4, "cache_read": 2, "cache_write": 0}}
    assert metrics.histograms_named("part.stage_duration_seconds")


def test_usage_report_builds_csv(tmp_path: Path) -> None:
    source = tmp_path / "logs.jsonl"
    output = tmp_path / "report.csv"
    entry = {
        "event": "part.summary",
        "part_id": "p",
        "document_id": "d",
        "duration_s": 2,
        "cost_usd": 0.1,
        "usage": {"x": {"input": 10, "cache_read": 2}},
    }
    source.write_text(json.dumps({"line": json.dumps(entry)}) + "\n", encoding="utf-8")
    rows, skipped = read_summaries(source)
    summary = write_report(rows, output, skipped)
    assert summary["parts"] == 1
    assert summary["cost_p95"] == 0.1
    assert "tokens_x_cache_read" in output.read_text(encoding="utf-8")


def test_prices_and_all_usage_fields() -> None:
    assert get_model_pricing("anthropic/claude-sonnet-5.5") == get_model_pricing("claude-sonnet-5-5-20261001")
    tracker = UsageTracker(part_id="p", document_id="d")
    tracker.add(
        purpose="x",
        model="claude-sonnet-5-5",
        usage=TokenUsage(
            input_tokens=1000, output_tokens=100, cache_read_input_tokens=3357, cache_creation_input_tokens=50
        ),
    )
    assert tracker.summary().cost_usd == 0.003461
    tracker.add(purpose="x", model="unknown", usage=TokenUsage(input_tokens=1, output_tokens=1))
    assert tracker.summary().cost_usd is None


async def test_tracker_is_shared_by_child_tasks_and_reset() -> None:
    tracker = UsageTracker(part_id="p", document_id="d")

    async def child() -> None:
        current = get_usage_tracker()
        assert current is tracker
        current.add(purpose="main", model="llama3.2", usage=TokenUsage(2, 1))

    with bind_usage_tracker(tracker):
        async with asyncio.TaskGroup() as group:
            group.create_task(child())
            group.create_task(child())
    assert get_usage_tracker() is None
    assert tracker.summary().usage["main"]["input"] == 4


def test_report_handles_duplicates_bad_lines_unknown_cost_and_percentiles(tmp_path: Path) -> None:
    source, output = tmp_path / "input", tmp_path / "out.csv"
    rows: list[dict[str, object]] = [
        {
            "event": "part.summary",
            "part_id": str(i),
            "document_id": "d",
            "duration_s": duration,
            "cost_usd": None if i == 0 else float(i),
            "usage": {},
            "stage_durations": {},
        }
        for i, duration in enumerate((10, 20, 300))
    ]
    source.write_text("\n".join([*(json.dumps(row) for row in rows), json.dumps(rows[0]), "", "bad"]), encoding="utf-8")
    parsed, skipped = read_summaries(source)
    result = write_report(parsed, output, skipped)
    assert result["parts"] == 3 and result["skipped"] == 3
    assert result["duration_p95"] == 300 and result["cost_p95"] == 2
    assert result["unknown_cost_parts"] == 1


def test_report_rejects_invalid_stage_values_and_boolean_numbers(tmp_path: Path) -> None:
    source = tmp_path / "input.jsonl"
    base: dict[str, object] = {
        "event": "part.summary",
        "document_id": "d",
        "part_id": "p",
        "duration_s": 1,
        "cost_usd": 0.1,
        "usage": {"x": {"input": 1}},
        "stage_durations": {},
    }
    bad = [
        {**base, "stage_durations": {"main": "bad"}},
        {**base, "duration_s": True},
        {**base, "cost_usd": False},
        {**base, "usage": {"x": {"input": True}}},
        {**base, "stage_durations": {"main": True}},
    ]
    source.write_text("\n".join(json.dumps(row) for row in [*bad, base]), encoding="utf-8")
    rows, skipped = read_summaries(source)
    assert len(rows) == 1 and skipped == len(bad)
    assert rows[0].usage["x"].input == 1


@pytest.mark.parametrize("field", ["duration_s", "cost_usd", "stage_durations"])
def test_report_skips_overflow_and_writes_next_valid_row(tmp_path: Path, field: str) -> None:
    source, output = tmp_path / "input.jsonl", tmp_path / "report.csv"
    valid: dict[str, object] = {
        "event": "part.summary",
        "document_id": "d",
        "part_id": "valid",
        "duration_s": 1,
        "cost_usd": 0.1,
        "usage": {},
        "stage_durations": {},
    }
    bad = {**valid, "part_id": "bad", field: {"main": 10**400} if field == "stage_durations" else 10**400}
    source.write_text("\n".join(json.dumps(row) for row in (bad, valid)), encoding="utf-8")
    rows, skipped = read_summaries(source)
    summary = write_report(rows, output, skipped)
    assert summary["skipped"] == 1
    with output.open(newline="", encoding="utf-8") as stream:
        written = list(csv.DictReader(stream))
    assert len(written) == 1 and written[0]["part_id"] == "valid"
