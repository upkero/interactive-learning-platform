"""ORM model of widget text descriptions with pgvector embeddings."""

import uuid
from datetime import datetime
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, ForeignKey, Index, Text, false, func
from sqlalchemy.orm import Mapped, mapped_column

from src.app.models.base import Base

# Dimension of the embedding model used across the platform.
EMBEDDING_DIM = 1024


class WidgetDescription(Base):
    """A natural-language description of a widget used for vector search."""

    __tablename__ = "widget_descriptions"
    __table_args__ = (
        Index("ix_widget_descriptions_widget_id", "widget_id"),
        Index(
            "ix_widget_descriptions_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 128},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    widget_id: Mapped[UUID] = mapped_column(ForeignKey("widgets.id", ondelete="CASCADE"))
    text: Mapped[str] = mapped_column(Text)
    is_paraphrase: Mapped[bool] = mapped_column(Boolean, server_default=false())
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
