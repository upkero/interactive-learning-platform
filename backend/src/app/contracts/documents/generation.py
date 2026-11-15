"""Commands and results for starting document generation."""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID


@dataclass(frozen=True, slots=True)
class GenerationAnswers:
    level: Literal["novice", "intermediate", "advanced"]
    goal: Literal["exam", "understand", "refresh"]
    depth: Literal["overview", "standard", "deep"]

    def as_dict(self) -> dict[str, str]:
        """The profile stored on every part and in ``users.last_answers``."""
        return {"level": self.level, "goal": self.goal, "depth": self.depth}


@dataclass(frozen=True, slots=True)
class GenerationCommand:
    user_id: UUID
    document_id: UUID
    topic_ids: tuple[str, ...]
    answers: GenerationAnswers


@dataclass(frozen=True, slots=True)
class GenerationStarted:
    document_id: UUID
    part_ids: tuple[UUID, ...]
    cost: int
    available: int
