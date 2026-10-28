"""Immutable contracts of the document aggregate."""

from src.app.contracts.documents.document_record import DocumentRecord
from src.app.contracts.documents.image_draft import ImageDraft
from src.app.contracts.documents.image_record import ImageRecord
from src.app.contracts.documents.material_record import MaterialRecord
from src.app.contracts.documents.part_draft import PartDraft
from src.app.contracts.documents.part_record import PartRecord
from src.app.contracts.documents.statuses import (
    DocumentStatus,
    MaterialRole,
    PartStatus,
    SourceType,
)

__all__ = [
    "DocumentRecord",
    "DocumentStatus",
    "ImageDraft",
    "ImageRecord",
    "MaterialRecord",
    "MaterialRole",
    "PartDraft",
    "PartRecord",
    "PartStatus",
    "SourceType",
]
