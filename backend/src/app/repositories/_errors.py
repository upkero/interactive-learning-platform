"""Helpers for translating PostgreSQL ``IntegrityError`` into domain errors."""

from sqlalchemy.exc import IntegrityError


def constraint_name(exc: IntegrityError) -> str | None:
    """Return the PostgreSQL constraint name behind an ``IntegrityError``.

    asyncpg reports the violated constraint on the wrapped Postgres error
    (``exc.orig.__cause__.constraint_name``). The naming convention keeps
    constraint names stable, so repositories can branch on them: only the
    constraint a repository "owns" may map to its specific domain error,
    everything else must fall back to the generic area error.
    """
    orig = exc.orig
    cause = orig.__cause__ if orig is not None else None
    if cause is None:
        return None
    name = getattr(cause, "constraint_name", None)
    return name if isinstance(name, str) else None
