"""ORM model of the primitives catalog (mirrors @grasp/primitives)."""

from datetime import datetime
from typing import Any

from sqlalchemy import String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from src.app.models.base import Base


class Primitive(Base):
    """A React primitive exported from the @grasp/primitives package."""

    __tablename__ = "primitives"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    version: Mapped[str] = mapped_column(String(32))
    description: Mapped[str] = mapped_column(Text)
    modes: Mapped[list[str]] = mapped_column(ARRAY(Text()))
    params_schema: Mapped[dict[str, Any]]
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())
