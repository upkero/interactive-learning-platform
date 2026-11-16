"""Read-side result for a document part."""

from dataclasses import dataclass

from src.app.contracts.documents.part_record import PartRecord


@dataclass(frozen=True, slots=True)
class PartDetails:
    part: PartRecord
    content: dict[str, object] | None
