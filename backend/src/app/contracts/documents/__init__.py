"""Immutable contracts of the document aggregate."""

from src.app.contracts.documents.document_details import DocumentDetails
from src.app.contracts.documents.document_record import DocumentRecord
from src.app.contracts.documents.image_draft import ImageDraft
from src.app.contracts.documents.image_record import ImageRecord
from src.app.contracts.documents.material_record import MaterialRecord
from src.app.contracts.documents.part_draft import PartDraft
from src.app.contracts.documents.part_record import PartRecord
from src.app.contracts.documents.readable_document import ReadableDocument
from src.app.contracts.documents.recovery_outcome import RecoveryOutcome
from src.app.contracts.documents.shared_user_info import SharedUserInfo
from src.app.contracts.documents.statuses import (
    DocumentErrorCode,
    DocumentStatus,
    MaterialRole,
    PartStatus,
    SourceType,
)
from src.app.contracts.documents.topic_node import TopicNode, topic_roots

__all__ = [
    "DocumentDetails",
    "DocumentErrorCode",
    "DocumentRecord",
    "DocumentStatus",
    "ImageDraft",
    "ImageRecord",
    "MaterialRecord",
    "MaterialRole",
    "PartDraft",
    "PartRecord",
    "PartStatus",
    "ReadableDocument",
    "RecoveryOutcome",
    "SharedUserInfo",
    "SourceType",
    "TopicNode",
    "topic_roots",
]
