"""Immutable contracts of the quota ledger."""

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
