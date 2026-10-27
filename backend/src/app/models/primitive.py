"""ORM model of the primitives catalog (mirrors @grasp/primitives)."""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.app.models.base import Base


class Primitive(Base):
    """A React primitive exported from the @grasp/primitives package."""

    __tablename__ = "primitives"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    version: Mapped[str] = mapped_column(String(32))
    description: Mapped[str] = mapped_column(Text)
    modes: Mapped[list[str]] = mapped_column(ARRAY(Text()))
    params_schema: Mapped[dict[str, Any]] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
