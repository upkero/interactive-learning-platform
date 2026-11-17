"""Task-local structured logging context."""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

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
