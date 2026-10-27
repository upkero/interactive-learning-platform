"""ORM model of widgets (both config- and code-generated kinds)."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.app.models.base import Base


class Widget(Base):
    """An interactive widget attached to a document part.

    Two kinds share this table:
    - config: rendered as a React primitive configuration;
    - code:   LLM-generated TSX compiled into standalone JS (sandboxed iframe).
    The CHECK constraint keeps the kind-specific fields consistent.
    """

    __tablename__ = "widgets"
    __table_args__ = (
        CheckConstraint("kind IN ('config', 'code')", name="ck_widgets_kind"),
        CheckConstraint("status IN ('active', 'excluded')", name="ck_widgets_status"),
        CheckConstraint(
            "(kind = 'config' AND primitive_id IS NOT NULL AND mode IS NOT NULL AND params IS NOT NULL) OR "
            "(kind = 'code' AND source_tsx IS NOT NULL AND compiled_js IS NOT NULL)",
            name="ck_widgets_kind_fields",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(16))
    primitive_id: Mapped[str | None] = mapped_column(ForeignKey("primitives.id", ondelete="SET NULL"))
    mode: Mapped[str | None] = mapped_column(String(32))
    params: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    source_tsx: Mapped[str | None] = mapped_column(Text)
    compiled_js: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), server_default="active")
    canonical_id: Mapped[UUID | None] = mapped_column(ForeignKey("widgets.id", ondelete="SET NULL"))
    version: Mapped[int] = mapped_column(Integer, server_default="1")
    created_from_part_id: Mapped[UUID | None] = mapped_column(ForeignKey("document_parts.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
