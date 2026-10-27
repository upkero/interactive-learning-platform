"""ORM model of the quota ledger (financial journal of reserving/charging refunds)."""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    ForeignKey,
    Identity,
    Index,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.app.models.base import Base


class GenerationLedger(Base):
    """Append-only journal of quota operations for billing and reports.

    - reserve: negative delta, holds quota for an attempt;
    - charge:  zero delta, burns the reserved amount;
    - refund:  positive delta, returns the reserved amount.
    """

    __tablename__ = "generation_ledger"
    __table_args__ = (
        CheckConstraint(
            "op IN ('reserve', 'charge', 'refund')",
            name="ck_generation_ledger_op",
        ),
        Index("ix_generation_ledger_user_id_period_start", "user_id", "period_start"),
        Index(
            "uq_generation_ledger_part_id_op",
            "part_id",
            "op",
            unique=True,
            postgresql_where=text("part_id IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    document_id: Mapped[UUID | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"))
    part_id: Mapped[UUID | None] = mapped_column(ForeignKey("document_parts.id", ondelete="SET NULL"))
    op: Mapped[str] = mapped_column(String(8))
    delta: Mapped[int]
    period_start: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
