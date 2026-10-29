"""Statuses and kinds of the widget library as StrEnum with DB-safe values."""

from enum import StrEnum


class WidgetKind(StrEnum):
    CONFIG = "config"
    CODE = "code"


class WidgetStatus(StrEnum):
    ACTIVE = "active"
    EXCLUDED = "excluded"


class UsageStatus(StrEnum):
    READY = "ready"
    PENDING = "pending"
    FALLBACK = "fallback"


class ReportReason(StrEnum):
    WRONG = "wrong"
    BROKEN = "broken"
    OTHER = "other"
