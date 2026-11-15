"""Errors of the widgets area."""

from src.app.exceptions.base import BaseAppException


class WidgetsError(BaseAppException):
    """Base class of every widgets area error."""


class WidgetNotFoundError(WidgetsError):
    status_code = 404
    public = True
    error_code = "widget_not_found"
    default_detail = "Widget not found."


class WidgetsIntegrityError(WidgetsError):
    """Base exception for widget integrity violations."""

    error_code = "widgets_integrity_error"
    default_detail = "Widget integrity constraint violated."


class WidgetConstraintError(WidgetsIntegrityError):
    """Widget data violates the kind-specific field consistency CHECK."""

    status_code = 422
    error_code = "widget_constraint"
    default_detail = "Widget fields are inconsistent with its kind."


class WidgetUsageDuplicateError(WidgetsIntegrityError):
    """The same directive slot of a part already has a usage."""

    status_code = 409
    error_code = "widget_usage_duplicate"
    default_detail = "A usage for this directive slot already exists."
