"""Decision events and metrics for widget moderation."""

import logging

from src.app.interfaces.observability.metrics_collector import MetricsCollector


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
