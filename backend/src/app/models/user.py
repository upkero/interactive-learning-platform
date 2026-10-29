"""ORM model of users."""

import uuid
from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import String, Text, func, true
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column

from src.app.models.base import Base


class User(Base):
    """Registered platform user with a monthly generation quota."""

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(CITEXT(), unique=True)
    password_hash: Mapped[str] = mapped_column(Text())
    display_name: Mapped[str | None] = mapped_column(String(100))
    locale: Mapped[str] = mapped_column(String(5), server_default="ru")
    monthly_limit: Mapped[int] = mapped_column(server_default="20")
    period_anchor: Mapped[date | None]
    profile: Mapped[dict[str, Any]] = mapped_column(server_default="{}")
    notify_email: Mapped[bool] = mapped_column(server_default=true())
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
