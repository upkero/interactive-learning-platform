"""Structured per-part accounting for decision logs and reports."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class PartSummary:
    document_id: str
    part_id: str
    duration_s: float
    stage_durations: dict[str, float]
    usage: dict[str, dict[str, int]]
    usage_by_model: dict[str, dict[str, dict[str, int]]]
    cost_usd: float | None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
