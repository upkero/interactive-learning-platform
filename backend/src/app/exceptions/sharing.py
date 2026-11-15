"""Errors from material sharing."""

from src.app.exceptions.base import BaseAppException


class RecipientNotRegisteredError(BaseAppException):
    status_code = 422
    error_code = "recipient_not_registered"
    default_detail = "Recipient is not registered."


class ShareWithSelfError(BaseAppException):
    status_code = 422
    error_code = "share_with_self"
    default_detail = "Cannot share with yourself."
