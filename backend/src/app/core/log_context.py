"""Task-local structured logging context."""

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from src.app.core.request_id import get_request_id

_context: ContextVar[dict[str, str] | None] = ContextVar("log_context", default=None)


def get_log_context() -> dict[str, str]:
    return _context.get() or {}


@contextmanager
def bind_log_context(**values: str) -> Iterator[None]:
    token = _context.set({**get_log_context(), **values})
    try:
        yield
    finally:
        _context.reset(token)


class LogContextFilter(logging.Filter):
    """Add request and entity identifiers to every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id() or "-"
        context = get_log_context()
        for field in ("user_id", "document_id", "part_id"):
            if not hasattr(record, field):
                setattr(record, field, context.get(field, "-"))
        return True
