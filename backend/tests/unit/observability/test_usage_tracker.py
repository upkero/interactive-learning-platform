import json
import subprocess
import sys

import pytest

from src.app.contracts.llm.token_usage import TokenUsage
from src.app.observability.usage_tracker import UsageTracker
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
    assert summary["part_id"] == "part"
    assert summary["usage"] == {"resolver": {"input": 10, "output": 4, "cache_read": 2, "cache_write": 0}}
    assert metrics.histograms_named("part.stage_duration_seconds")


def test_usage_report_builds_csv(tmp_path) -> None:  # type: ignore[no-untyped-def]
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
    subprocess.run([sys.executable, "evals/usage_report.py", str(source), str(output)], check=True)
    assert "part_id" in output.read_text(encoding="utf-8")
