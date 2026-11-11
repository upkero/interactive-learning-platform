"""Documents area errors: DB integrity violations and upload validation."""

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


class MaterialAccessDuplicateError(DocumentsIntegrityError):
    """The user already has a material record for the document."""

    status_code = 409
    error_code = "material_access_duplicate"
    default_detail = "The user already has access to this document."


class UploadValidationError(BaseAppException):
    """Base exception for rejected uploads (file inspection, story 1.3.3)."""

    error_code = "upload_validation_error"
    default_detail = "The uploaded file was rejected."


class UnsupportedFileTypeError(UploadValidationError):
    """Content does not match a supported type (PDF/DOCX/Markdown) or is broken."""

    status_code = 415
    error_code = "unsupported_file_type"
    default_detail = "Unsupported file type."


class FileTooLargeError(UploadValidationError):
    """The file exceeds its size limit (413)."""

    status_code = 413
    error_code = "file_too_large"
    default_detail = "The file is too large."


class TooManyPagesError(UploadValidationError):
    """The PDF exceeds the page limit (422)."""

    status_code = 422
    error_code = "too_many_pages"
    default_detail = "The document has too many pages."
