"""Unit tests of the primitive membership catalog (story 2.3)."""

from datetime import datetime

from src.app.contracts.widgets import PrimitiveRecord
from src.app.services.solver.library.primitive_catalog import PrimitiveCatalog


def _record(primitive_id: str) -> PrimitiveRecord:
    return PrimitiveRecord(
        id=primitive_id,
        version="1.0.0",
        description="d",
        modes=["explore"],
        params_schema={},
        updated_at=datetime(2026, 1, 1),
    )


def test_catalog_membership() -> None:
    catalog = PrimitiveCatalog(["three-frame", "key-terms"])

    assert "three-frame" in catalog
    assert "key-terms" in catalog
    assert "missing" not in catalog
    assert 42 not in catalog
    assert catalog.ids == frozenset({"three-frame", "key-terms"})
    assert len(catalog) == 2


def test_catalog_from_records() -> None:
    catalog = PrimitiveCatalog.from_records([_record("a"), _record("b")])

    assert catalog.ids == frozenset({"a", "b"})


def test_empty_catalog_contains_nothing() -> None:
    catalog = PrimitiveCatalog()

    assert "anything" not in catalog
    assert len(catalog) == 0
