"""Immutable user record."""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True, slots=True)
class UserRecord:
    id: UUID
    email: str
    password_hash: str
    display_name: str | None
    locale: str
    monthly_limit: int
    period_anchor: date | None
    profile: dict[str, Any]
    notify_email: bool
    created_at: datetime
