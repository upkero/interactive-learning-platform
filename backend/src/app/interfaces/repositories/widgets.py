"""Protocols of the widget library and report repositories."""

from collections.abc import Sequence
from typing import Any, Protocol
from uuid import UUID

from src.app.contracts.widgets import (
    PrimitiveRecord,
    ReportReason,
    ReportRecord,
    UsageStatus,
    WidgetDescriptionRecord,
    WidgetKind,
    WidgetRecord,
    WidgetStatus,
    WidgetUsageDraft,
    WidgetUsageRecord,
)


class PrimitiveRepositoryProtocol(Protocol):
    """Public API of the primitives catalog access."""

    async def get(self, primitive_id: str) -> PrimitiveRecord | None: ...

    async def list_all(self) -> list[PrimitiveRecord]: ...

    async def upsert(
        self,
        *,
        primitive_id: str,
        version: str,
        description: str,
        modes: list[str],
        params_schema: dict[str, Any],
    ) -> PrimitiveRecord: ...


class WidgetRepositoryProtocol(Protocol):
    """Public API of the widgets table access."""

    async def get(self, widget_id: UUID) -> WidgetRecord | None: ...

    async def create(
        self,
        *,
        kind: WidgetKind,
        primitive_id: str | None = None,
        mode: str | None = None,
        params: dict[str, Any] | None = None,
        source_tsx: str | None = None,
        compiled_js: str | None = None,
        created_from_part_id: UUID | None = None,
    ) -> WidgetRecord: ...

    async def set_status(self, widget_id: UUID, status: WidgetStatus) -> None: ...


class WidgetDescriptionRepositoryProtocol(Protocol):
    """Public API of the widget_descriptions table access (write-only)."""

    async def create(
        self,
        *,
        widget_id: UUID,
        text: str,
        is_paraphrase: bool,
        embedding: list[float],
    ) -> WidgetDescriptionRecord: ...

    async def list_by_widget(self, widget_id: UUID) -> list[WidgetDescriptionRecord]: ...


class WidgetUsageRepositoryProtocol(Protocol):
    """Public API of the widget_usages table access."""

    async def get(self, usage_id: UUID) -> WidgetUsageRecord | None: ...

    async def add_many(self, part_id: UUID, usages: Sequence[WidgetUsageDraft]) -> list[WidgetUsageRecord]: ...

    async def set_status(self, usage_id: UUID, status: UsageStatus) -> None: ...


class ReportRepositoryProtocol(Protocol):
    """Public API of the reports table access."""

    async def get_by_widget_and_user(self, widget_id: UUID, user_id: UUID) -> ReportRecord | None: ...

    async def create_if_not_exists(
        self,
        *,
        widget_id: UUID,
        user_id: UUID,
        reason: ReportReason,
        part_id: UUID | None = None,
    ) -> ReportRecord | None: ...
