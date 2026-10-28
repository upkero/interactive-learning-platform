"""Integrity errors of the documents area (mapped from DB IntegrityError)."""

from src.app.exceptions.base import BaseAppException


class DocumentsIntegrityError(BaseAppException):
    """Base exception for document integrity violations."""

    error_code = "documents_integrity_error"
    default_detail = "Document integrity constraint violated."


class DocumentPartDuplicateError(DocumentsIntegrityError):
    """Two parts of the same document claim the same index."""

    status_code = 409
    error_code = "document_part_duplicate"
    default_detail = "A part with this index already exists in the document."
