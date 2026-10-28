"""Immutable record of the quota ledger and its operation kinds.

Delta semantics are defined by the quota ADR (story 1.6): ``reserve``
holds quota with a negative delta, ``charge`` burns it with zero delta,
``refund`` returns it with a positive delta.
"""

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from uuid import UUID


class LedgerOp(StrEnum):
    RESERVE = "reserve"
    CHARGE = "charge"
    REFUND = "refund"


@dataclass(frozen=True, slots=True)
class LedgerEntry:
    id: int
    user_id: UUID
    document_id: UUID | None
    part_id: UUID | None
    op: LedgerOp
    delta: int
    period_start: date
    created_at: datetime
