"""ORM model of images extracted from documents."""

from uuid import UUID

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.app.models.base import Base


class Image(Base):
    """An image referenced by a document and stored in MinIO."""

    __tablename__ = "images"
    __table_args__ = (Index("ix_images_document_id", "document_id"),)

    id: Mapped[UUID] = mapped_column(primary_key=True)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    object_key: Mapped[str] = mapped_column(Text)
    page: Mapped[int | None] = mapped_column(Integer)
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    caption: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    topic_id: Mapped[str | None] = mapped_column(String(64))
