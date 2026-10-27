"""Immutable contracts of widgets, primitives and reports."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from src.app.contracts.documents.statuses import PartStatus


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
    UGLY = "ugly"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class PrimitiveRecord:
    id: str
    version: str
    description: str
    modes: list[str]
    params_schema: dict[str, Any]
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class WidgetRecord:
    id: UUID
    kind: WidgetKind
    primitive_id: str | None
    mode: str | None
    params: dict[str, Any] | None
    source_tsx: str | None
    compiled_js: str | None
    status: WidgetStatus
    canonical_id: UUID | None
    version: int
    created_from_part_id: UUID | None
    created_at: datetime
    # Auxiliary marker for service code and seed data
    part_status: PartStatus | None = None


@dataclass(frozen=True, slots=True)
class WidgetDescriptionRecord:
    id: UUID
    widget_id: UUID
    text: str
    is_paraphrase: bool
    embedding: list[float]
    created_at: datetime


@dataclass(frozen=True, slots=True)
class WidgetUsageRecord:
    id: UUID
    part_id: UUID
    widget_id: UUID | None
    directive_ref: str
    params: dict[str, Any] | None
    position: int
    status: UsageStatus
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ReportRecord:
    id: UUID
    widget_id: UUID
    user_id: UUID
    part_id: UUID | None
    reason: ReportReason
    comment: str | None
    created_at: datetime
