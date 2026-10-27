"""Unit tests: contracts StrEnum values vs model CHECK constraints."""

import pytest
from sqlalchemy import CheckConstraint

from src.app.contracts.documents.statuses import (
    DocumentStatus,
    MaterialRole,
    PartStatus,
    SourceType,
)
from src.app.contracts.quota import LedgerOp
from src.app.contracts.widgets import ReportReason, UsageStatus, WidgetKind, WidgetStatus
from src.app.models import (
    Base,
    Document,
    DocumentPart,
    GenerationLedger,
    Report,
    UserMaterial,
    Widget,
    WidgetUsage,
)

pytestmark = pytest.mark.unit


# Model -> CHECK constraint name -> enum whose values must match the CHECK
_PAIRS: list[tuple[type[object], str, type[object]]] = [
    (Document, "ck_documents_source_type", SourceType),
    (Document, "ck_documents_status", DocumentStatus),
    (DocumentPart, "ck_document_parts_status", PartStatus),
    (UserMaterial, "ck_user_materials_role", MaterialRole),
    (Widget, "ck_widgets_kind", WidgetKind),
    (Widget, "ck_widgets_status", WidgetStatus),
    (WidgetUsage, "ck_widget_usages_status", UsageStatus),
    (Report, "ck_reports_reason", ReportReason),
    (GenerationLedger, "ck_generation_ledger_op", LedgerOp),
]

EXPECTED_TABLES = {
    "users",
    "documents",
    "document_parts",
    "images",
    "user_materials",
    "primitives",
    "widgets",
    "widget_descriptions",
    "widget_usages",
    "reports",
    "quiz_attempts",
    "generation_ledger",
}


def test_base_metadata_declares_twelve_tables() -> None:
    """Base.metadata must declare exactly the 12 tables of Story 1.2."""
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_strenum_values_match_check_constraints() -> None:
    """Every CHECK constraint in models must accept exactly the StrEnum values."""
    for model, constraint_name, enum in _PAIRS:
        table = model.__table__  # type: ignore[attr-defined]
        constraint = next(c for c in table.constraints if isinstance(c, CheckConstraint) and c.name == constraint_name)
        sql = str(constraint.sqltext)
        allowed = {v.strip().strip("'") for v in sql.split("IN (")[1].rsplit(")", 1)[0].split(",")}
        expected = {member.value for member in enum}  # type: ignore[attr-defined]
        assert allowed == expected, f"{table.name}.{constraint_name} mismatch vs {enum.__name__}"
