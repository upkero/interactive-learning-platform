"""Unit tests for widget model consistency (checks mirror the DB schema)."""

import pytest
from sqlalchemy import CheckConstraint

from src.app.models import Widget

pytestmark = pytest.mark.unit


def test_widget_kind_fields_check_present() -> None:
    """The consistency CHECK for kind-specific fields must exist on the parent."""
    constraints = Widget.metadata.tables["widgets"].constraints
    constraint = next(c for c in constraints if isinstance(c, CheckConstraint) and c.name == "ck_widgets_kind_fields")
    sql = str(constraint.sqltext)
    assert "(kind = 'config'" in sql
    assert "source_tsx IS NOT NULL" in sql
    assert "compiled_js IS NOT NULL" in sql
