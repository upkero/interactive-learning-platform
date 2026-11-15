"""Commands and results for starting document generation."""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID


@dataclass(frozen=True, slots=True)
class GenerationAnswers:
    level: Literal["novice", "intermediate", "advanced"]
    goal: Literal["exam", "understand", "refresh"]
    depth: Literal["overview", "standard", "deep"]


@dataclass(frozen=True, slots=True)
class GenerationStarted:
    document_id: UUID
    part_ids: tuple[UUID, ...]
    cost: int
    available: int
