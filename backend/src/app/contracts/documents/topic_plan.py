"""Preview of planned document parts."""

from dataclasses import dataclass

from src.app.contracts.documents.part_plan import PartPlan


@dataclass(frozen=True, slots=True)
class TopicPlan:
    parts: tuple[PartPlan, ...]
