"""Decision events and metrics for widget moderation."""

import logging
from typing import Literal

from src.app.interfaces.observability.metrics_collector import MetricsCollector

ResolverDecision = Literal["reused", "configured", "generated", "fallback"]


class DecisionLog:
    def __init__(self, *, metrics: MetricsCollector, logger: logging.Logger | None = None) -> None:
        self._metrics = metrics
        self._logger = logger or logging.getLogger("grasp.decisions")

    def widget_excluded(self, *, widget_id: str, reporters: int, threshold: int) -> None:
        self._metrics.increment_counter("widgets.excluded")
        self._logger.info(
            "Widget excluded.",
            extra={"event": "widget.excluded", "widget_id": widget_id, "reporters": reporters, "threshold": threshold},
        )

    def resolver_decision(
        self,
        *,
        directive_ref: str,
        decision: ResolverDecision,
        widget_id: str | None,
        candidates: list[tuple[str, float]],
        reason: str,
        duration_ms: int,
    ) -> None:
        self._metrics.increment_counter("resolver.decisions", labels={"decision": decision})
        self._logger.info(
            "Resolver decision.",
            extra={
                "event": "resolver.decision",
                "directive_ref": directive_ref,
                "decision": decision,
                "widget_id": widget_id,
                "candidates": [{"id": item, "distance": round(distance, 4)} for item, distance in candidates],
                "reason": reason[:500],
                "duration_ms": duration_ms,
            },
        )

    def judge_verdict(self, *, widget_ref: str, attempt: int, accepted: bool, issues: list[str]) -> None:
        self._metrics.increment_counter(
            "judge.verdicts", labels={"accepted": str(accepted).lower(), "attempt": str(attempt)}
        )
        self._logger.info(
            "Judge verdict.",
            extra={
                "event": "judge.verdict",
                "widget_ref": widget_ref,
                "attempt": attempt,
                "accepted": accepted,
                "issues": issues[:10],
            },
        )

    def quiz_check(self, *, quiz_type: str, result: Literal["kept", "rewritten", "dropped"], reason: str) -> None:
        self._metrics.increment_counter("quiz.checks", labels={"type": quiz_type, "result": result})
        self._logger.info(
            "Quiz check.", extra={"event": "quiz.check", "type": quiz_type, "result": result, "reason": reason[:500]}
        )

    def library_merge(
        self,
        *,
        canonical_id: str | None,
        merged_ids: list[str],
        rejected_ids: list[str],
        reason: str,
        dry_run: bool,
    ) -> None:
        outcome = "merged" if canonical_id else "rejected"
        self._metrics.increment_counter("library.merges", labels={"outcome": outcome})
        self._logger.info(
            "Library merge.",
            extra={
                "event": "library.merge",
                "canonical_id": canonical_id,
                "merged_ids": merged_ids,
                "rejected_ids": rejected_ids,
                "reason": reason[:500],
                "dry_run": dry_run,
            },
        )
