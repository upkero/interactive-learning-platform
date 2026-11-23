import logging

import pytest

from src.app.observability.decision_log import DecisionLog
from tests.support.fakes.observability.metrics_collector import RecordingMetricsCollector

pytestmark = pytest.mark.unit


def test_decision_log_writes_events_and_metrics(caplog: pytest.LogCaptureFixture) -> None:
    metrics = RecordingMetricsCollector()
    decisions = DecisionLog(metrics=metrics)

    with caplog.at_level(logging.INFO, logger="grasp.decisions"):
        decisions.resolver_decision(
            directive_ref="d-1",
            decision="reused",
            widget_id="w-1",
            candidates=[("w-1", 0.12345)],
            reason="close match",
            duration_ms=12,
        )
        decisions.judge_verdict(widget_ref="w-1", attempt=1, accepted=True, issues=[])
        decisions.quiz_check(quiz_type="single_choice", result="kept", reason="valid")
        decisions.widget_excluded(widget_id="w-1", reporters=3, threshold=3)
        decisions.library_merge(
            canonical_id="w-1", merged_ids=["w-2"], rejected_ids=[], reason="same", dry_run=False
        )

    assert [record.event for record in caplog.records] == [  # type: ignore[attr-defined]
        "resolver.decision",
        "judge.verdict",
        "quiz.check",
        "widget.excluded",
        "library.merge",
    ]
    assert "resolver.decisions" in metrics.counters
    assert "judge.verdicts" in metrics.counters
    assert "quiz.checks" in metrics.counters
    assert "widgets.excluded" in metrics.counters
    assert "library.merges" in metrics.counters
