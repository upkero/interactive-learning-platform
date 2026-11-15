"""Decision events and metrics for widget moderation."""

import logging
from uuid import UUID

from prometheus_client import Counter

widgets_excluded_total = Counter("widgets_excluded_total", "Widgets excluded after user reports")


class DecisionLog:
    def widget_excluded(self, *, widget_id: UUID, reporters: int, threshold: int) -> None:
        logging.getLogger("grasp.decisions").info(
            "widget.excluded",
            extra={
                "event": "widget.excluded",
                "widget_id": str(widget_id),
                "reporters": reporters,
                "threshold": threshold,
            },
        )
        widgets_excluded_total.inc()
