"""Queue (Celery/Redis) errors surfaced as 503 (story 1.5)."""

from src.app.exceptions.base import BaseAppException


class TasksError(BaseAppException):
    """Base class of every queue layer error."""


class TaskDispatchError(TasksError):
    """The broker refused or lost a task; the client may retry later."""

    status_code = 503
    error_code = "queue_unavailable"
    default_detail = "The task queue is temporarily unavailable."
