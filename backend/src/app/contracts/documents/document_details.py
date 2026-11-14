"""Aggregated view of a document for GET /documents/{id} (story 1.4.3).

The service assembles the pieces (record, role, source link, parts,
who it is shared with) into this contract; the router converts it into
the ``DocumentOut`` schema.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.app.contracts.documents.document_record import DocumentRecord
from src.app.contracts.documents.part_record import PartRecord
from src.app.contracts.documents.statuses import MaterialRole


@dataclass(frozen=True, slots=True)
class SharedUserInfo:
    """A registered user the document was shared with."""

    user_id: UUID
    email: str
    display_name: str | None
    shared_at: datetime


@dataclass(frozen=True, slots=True)
class DocumentDetails:
    document: DocumentRecord
    role: MaterialRole
    # presigned URL of the source file (upload) or the original gdocs link
    source_url: str | None
    parts: tuple[PartRecord, ...]
    # filled only for the owner; shared users see an empty tuple
    shared_with: tuple[SharedUserInfo, ...]
