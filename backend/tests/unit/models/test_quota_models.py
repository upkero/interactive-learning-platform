"""Unit tests for quota-related DB guarantees mirrored in models."""

import pytest
from sqlalchemy import Index

from src.app.models import GenerationLedger

pytestmark = pytest.mark.unit


def test_ledger_partial_unique_index_defined() -> None:
    """A unique (part_id, op) index scoped to non-null part_id must exist."""
    index = next(
        i
        for i in GenerationLedger.metadata.tables["generation_ledger"].indexes
        if isinstance(i, Index) and i.name == "uq_generation_ledger_part_id_op"
    )
    assert index.unique is True
    pg_options = index.dialect_options["postgresql"]
    assert "part_id IS NOT NULL" in str(pg_options.get("where"))
