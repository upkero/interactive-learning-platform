"""Object storage errors (mapped from boto3 errors)."""

from src.app.exceptions.base import BaseAppException


class ObjectStorageError(BaseAppException):
    """Base exception for object storage operations."""

    status_code = 502
    error_code = "object_storage_error"
    default_detail = "Object storage operation failed."


class ObjectNotFoundError(ObjectStorageError):
    """Raised when the requested object does not exist."""

    status_code = 404
    error_code = "object_not_found"
    default_detail = "Object not found."
