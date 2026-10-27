"""Immutable record of user access rights to a document."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.app.contracts.documents.statuses import MaterialRole


@dataclass(frozen=True, slots=True)
class MaterialRecord:
    user_id: UUID
    document_id: UUID
    role: MaterialRole
    shared_by: UUID | None
    created_at: datetime
