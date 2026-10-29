"""Immutable contracts of widgets, primitives and reports."""

from src.app.contracts.widgets.primitive_record import PrimitiveRecord
from src.app.contracts.widgets.report_record import ReportRecord
from src.app.contracts.widgets.statuses import ReportReason, UsageStatus, WidgetKind, WidgetStatus
from src.app.contracts.widgets.widget_description_record import WidgetDescriptionRecord
from src.app.contracts.widgets.widget_record import WidgetRecord
from src.app.contracts.widgets.widget_usage_draft import WidgetUsageDraft
from src.app.contracts.widgets.widget_usage_record import WidgetUsageRecord

__all__ = [
    "PrimitiveRecord",
    "ReportReason",
    "ReportRecord",
    "UsageStatus",
    "WidgetDescriptionRecord",
    "WidgetKind",
    "WidgetRecord",
    "WidgetStatus",
    "WidgetUsageDraft",
    "WidgetUsageRecord",
]
