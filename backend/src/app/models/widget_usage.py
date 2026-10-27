"""ORM model of widget placements on document pages."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.app.models.base import Base


class WidgetUsage(Base):
    """Binds a widget to a concrete directive slot of a document part."""

    __tablename__ = "widget_usages"
    __table_args__ = (
        UniqueConstraint("part_id", "directive_ref", name="uq_widget_usages_part_id_directive_ref"),
        CheckConstraint("status IN ('ready', 'pending', 'fallback')", name="ck_widget_usages_status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    part_id: Mapped[UUID] = mapped_column(ForeignKey("document_parts.id", ondelete="CASCADE"))
    widget_id: Mapped[UUID | None] = mapped_column(ForeignKey("widgets.id", ondelete="SET NULL"))
    directive_ref: Mapped[str] = mapped_column(String(64))
    params: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    position: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), server_default="pending")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
