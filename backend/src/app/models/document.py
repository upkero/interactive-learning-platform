"""ORM model of documents."""

import uuid
from collections.abc import Mapping
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from src.app.models.base import Base


class Document(Base):
    """A learning material uploaded by a user and kept in MinIO."""

    __tablename__ = "documents"
    # Server-generated values (created_at, updated_at onupdate) are fetched
    # via RETURNING during flush; otherwise they stay expired after an
    # UPDATE and reading them from sync code raises MissingGreenlet.
    __mapper_args__: Mapping[str, Any] = {"eager_defaults": True}
    __table_args__ = (
        CheckConstraint(
            "source_type IN ('upload', 'gdocs')",
            name="ck_documents_source_type",
        ),
        CheckConstraint(
            "status IN ('uploaded', 'parsing', 'parsed', 'generating', 'done', 'failed')",
            name="ck_documents_status",
        ),
        Index("ix_documents_owner_id", "owner_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(300))
    source_type: Mapped[str] = mapped_column(String(16))
    source_uri: Mapped[str | None] = mapped_column(Text)
    object_key: Mapped[str] = mapped_column(Text)
    mime_type: Mapped[str] = mapped_column(String(128))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    page_count: Mapped[int | None]
    checksum: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), server_default="uploaded")
    topic_tree: Mapped[dict[str, Any] | None]
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
