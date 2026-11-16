"""Documents area errors: access, processing limits, upload validation, integrity."""

from src.app.exceptions.base import BaseAppException


class DocumentsError(BaseAppException):
    """Base class of every documents area error."""


class DocumentNotFoundError(DocumentsError):
    """The document does not exist or is not accessible by this user.

    404 instead of 403: a foreign document must not be distinguishable
    from a missing one.
    """

    status_code = 404
    public = True
    error_code = "document_not_found"
    default_detail = "Document not found."


class PartNotFoundError(DocumentsError):
    status_code = 404
    public = True
    error_code = "part_not_found"
    default_detail = "Part not found."


class DocumentNotReadyError(DocumentsError):
    """The document is not ready for the requested read/plan operation.

    The document is still in ``uploaded``/``parsing`` (the caller gets
    the current status in ``extra``) or ``failed`` (the caller gets the
    parse error code in ``extra["reason"]``).
    """

    status_code = 409
    public = True
    error_code = "document_not_ready"
    default_detail = "The document is not parsed yet."


class ProcessingLimitError(DocumentsError):
    """The user already has the maximum number of documents in processing."""

    status_code = 429
    public = True
    error_code = "processing_limit_reached"
    default_detail = "Too many documents are currently being processed."


class DocumentsIntegrityError(DocumentsError):
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


class UploadValidationError(DocumentsError):
    """Base exception for rejected uploads (file inspection, story 1.3.3)."""

    error_code = "upload_validation_error"
    default_detail = "The uploaded file was rejected."


class UnsupportedFileTypeError(UploadValidationError):
    """Content does not match a supported type (PDF/DOCX/Markdown) or is broken."""

    status_code = 415
    public = True
    error_code = "unsupported_file_type"
    default_detail = "Unsupported file type."


class FileTooLargeError(UploadValidationError):
    """The file exceeds its size limit (413)."""

    status_code = 413
    public = True
    error_code = "file_too_large"
    default_detail = "The file is too large."


class TooManyPagesError(UploadValidationError):
    """The PDF exceeds the page limit (422)."""

    status_code = 422
    public = True
    error_code = "too_many_pages"
    default_detail = "The document has too many pages."


class InvalidGdocsUrlError(DocumentsError):
    """The import link is not a public Google Docs document URL (422).

    Only ``https://docs.google.com/document/d/{id}...`` is accepted:
    other domains and other Google products (Sheets, Slides) are refused
    before any network activity (story 1.4.4, SSRF-safe).
    """

    status_code = 422
    public = True
    error_code = "invalid_gdocs_url"
    default_detail = "The URL must point to a Google Docs document."


class EmptyTopicSelectionError(DocumentsError):
    """The plan/generate request selected no topics (422)."""

    status_code = 422
    public = True
    error_code = "empty_topic_selection"
    default_detail = "Select at least one topic."


class UnknownTopicError(DocumentsError):
    """A selected topic id does not exist in the document's tree (422)."""

    status_code = 422
    public = True
    error_code = "unknown_topic"
    default_detail = "The topic is not part of this document."
