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
        decisions.library_merge(canonical_id="w-1", merged_ids=["w-2"], rejected_ids=[], reason="same", dry_run=False)

    assert [record.event for record in caplog.records] == [  # type: ignore[attr-defined]
        "resolver.decision",
        "judge.verdict",
        "quiz.check",
        "widget.excluded",
        "library.merge",
    ]
    assert "resolver.decisions" in metrics.counters
    assert "judge.verdicts" in metrics.counters
    assert "quiz.generated" in metrics.counters
    assert "widgets.excluded" in metrics.counters
    assert "library.merges" in metrics.counters
    assert metrics.labeled_counters == [
        ("resolver.decisions", {"decision": "reused"}, 1),
        ("judge.verdicts", {"accepted": "true", "attempt": "1"}, 1),
        ("quiz.generated", {"type": "single_choice", "outcome": "kept"}, 1),
        ("widgets.excluded", {}, 1),
        ("library.merges", {"outcome": "merged"}, 1),
    ]
    assert caplog.records[0].__dict__["candidates"] == [{"id": "w-1", "distance": 0.1235}]


def test_decision_fields_are_bounded(caplog: pytest.LogCaptureFixture) -> None:
    decisions = DecisionLog(metrics=RecordingMetricsCollector())
    with caplog.at_level(logging.INFO, logger="grasp.decisions"):
        decisions.resolver_decision(
            directive_ref="d", decision="fallback", widget_id=None, candidates=[], reason="x" * 600, duration_ms=1
        )
        decisions.judge_verdict(widget_ref="w", attempt=2, accepted=False, issues=[str(i) for i in range(20)])
    assert len(caplog.records[0].__dict__["reason"]) == 500
    assert len(caplog.records[1].__dict__["issues"]) == 10
