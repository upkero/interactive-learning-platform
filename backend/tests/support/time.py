"""Shared clock helper for in-memory fakes."""

from datetime import UTC, datetime


def now() -> datetime:
    """Current UTC timestamp (single source for deterministic fakes)."""
    return datetime.now(UTC)
