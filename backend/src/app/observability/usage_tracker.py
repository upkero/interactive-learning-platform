"""Per-part token and stage accounting shared by child asyncio tasks."""

import logging
from collections import defaultdict
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from time import perf_counter

from src.app.contracts.llm.token_usage import TokenUsage
from src.app.core.settings.pricing import get_model_pricing
from src.app.interfaces.observability.metrics_collector import MetricsCollector

logger = logging.getLogger("grasp.usage")
_current: ContextVar["UsageTracker | None"] = ContextVar("usage_tracker", default=None)


@dataclass(slots=True)
class _Usage:
    input: int = 0
    output: int = 0
    cache_read: int = 0
    cache_write: int = 0


class UsageTracker:
    def __init__(self, *, part_id: str, document_id: str, metrics: MetricsCollector | None = None) -> None:
        self.part_id = part_id
        self.document_id = document_id
        self.metrics = metrics
        self.started = perf_counter()
        self._usage: dict[str, _Usage] = defaultdict(_Usage)
        self._stages: dict[str, float] = {}

    def add(self, *, purpose: str, model: str, usage: TokenUsage) -> None:
        item = self._usage[f"{purpose}:{model}"]
        item.input += usage.input_tokens
        item.output += usage.output_tokens
        item.cache_read += usage.cache_read_input_tokens
        item.cache_write += usage.cache_creation_input_tokens

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        started = perf_counter()
        try:
            yield
        finally:
            duration = perf_counter() - started
            self._stages[name] = self._stages.get(name, 0.0) + duration
            if self.metrics is not None:
                self.metrics.observe_histogram(
                    "part.stage_duration_seconds",
                    duration,
                    labels={"stage": name},
                    buckets=(10, 30, 60, 120, 180, 240, 300, 330),
                )

    def summary(self) -> dict[str, object]:
        by_purpose: dict[str, dict[str, int]] = {}
        cost = 0.0
        for key, usage in self._usage.items():
            purpose, model = key.split(":", 1)
            values = by_purpose.setdefault(purpose, {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0})
            values["input"] += usage.input
            values["output"] += usage.output
            values["cache_read"] += usage.cache_read
            values["cache_write"] += usage.cache_write
            prices = get_model_pricing(model)
            cost += (
                usage.input * prices.input
                + usage.output * prices.output
                + usage.cache_read * prices.cache_read
                + usage.cache_write * prices.cache_write
            ) / 1_000_000
        return {
            "document_id": self.document_id,
            "part_id": self.part_id,
            "duration_s": round(perf_counter() - self.started, 3),
            "stage_durations": self._stages,
            "usage": by_purpose,
            "cost_usd": round(cost, 6),
        }

    def emit_summary(self) -> None:
        logger.info("Part summary.", extra={"event": "part.summary", **self.summary()})


def get_usage_tracker() -> UsageTracker | None:
    return _current.get()


@contextmanager
def bind_usage_tracker(tracker: UsageTracker) -> Iterator[None]:
    token = _current.set(tracker)
    try:
        yield
    finally:
        _current.reset(token)
