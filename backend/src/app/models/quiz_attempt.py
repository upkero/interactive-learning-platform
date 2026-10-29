"""ORM model of quiz attempts."""

import uuid
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from src.app.models.base import Base


class QuizAttempt(Base):
    """A user answer to a single quiz key inside a document part."""

    __tablename__ = "quiz_attempts"
    __table_args__ = (Index("ix_quiz_attempts_user_id_part_id", "user_id", "part_id"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    part_id: Mapped[UUID] = mapped_column(ForeignKey("document_parts.id", ondelete="CASCADE"))
    quiz_key: Mapped[str] = mapped_column(String(12))
    answer: Mapped[dict[str, Any]]
    is_correct: Mapped[bool]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
