"""Read-side result for a document part."""

from dataclasses import dataclass

from src.app.contracts.documents.part_record import PartRecord
from src.app.contracts.documents.public_part_content import PublicPartContent


@dataclass(frozen=True, slots=True)
class PartDetails:
    part: PartRecord
    content: PublicPartContent | None
