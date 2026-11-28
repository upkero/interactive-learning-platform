"""Validated widget configuration (story 2.4)."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ValidConfig:
    """A widget configuration that passed jsonschema and mode validation."""

    primitive_id: str
    mode: str
    params: dict[str, Any]
    primitive_version: int

    @property
    def key(self) -> tuple[str, str, tuple[tuple[str, Any], ...]]:
        """Key for deduplication: (primitive_id, mode, sorted params)."""
        return (self.primitive_id, self.mode, tuple(sorted(self.params.items())))


__all__ = ["ValidConfig"]
