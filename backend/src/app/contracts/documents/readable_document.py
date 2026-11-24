"""Document data required by the progress stream."""

from dataclasses import dataclass

from src.app.contracts.documents.document_record import DocumentRecord


@dataclass(frozen=True, slots=True)
class ReadableDocument:
    document: DocumentRecord
    owner_locale: str
