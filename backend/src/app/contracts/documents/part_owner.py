"""Ownership of a part for quota accounting."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class PartOwner:
    user_id: UUID
    document_id: UUID
