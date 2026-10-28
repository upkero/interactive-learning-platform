"""ORM model of user reports against widgets."""

import uuid
from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from src.app.models.base import Base


class Report(Base):
    """A user complaint about a widget; one complaint per widget per user."""

    __tablename__ = "reports"
    __table_args__ = (
        UniqueConstraint("widget_id", "user_id", name="uq_reports_widget_id_user_id"),
        CheckConstraint("reason IN ('wrong', 'broken', 'other')", name="ck_reports_reason"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    widget_id: Mapped[UUID] = mapped_column(ForeignKey("widgets.id", ondelete="CASCADE"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    part_id: Mapped[UUID | None] = mapped_column(ForeignKey("document_parts.id", ondelete="SET NULL"))
    reason: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
