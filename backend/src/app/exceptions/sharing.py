"""Errors from material sharing."""

from src.app.exceptions.base import BaseAppException


class SharingError(BaseAppException):
    """Base class of every sharing error."""


class RecipientNotRegisteredError(SharingError):
    status_code = 422
    public = True
    error_code = "recipient_not_registered"
    default_detail = "Recipient is not registered."


class ShareWithSelfError(SharingError):
    status_code = 422
    public = True
    error_code = "share_with_self"
    default_detail = "Cannot share with yourself."
