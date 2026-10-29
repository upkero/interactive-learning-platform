"""initial schema with 12 tables, pgvector and citext

Revision ID: 0001
Revises: None
Create Date: 2026-10-19 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 0. PostgreSQL extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")

    # 1. Users table
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("email", postgresql.CITEXT(), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=True),
        sa.Column("locale", sa.String(5), nullable=False, server_default="ru"),
        sa.Column("monthly_limit", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("period_anchor", sa.Date(), nullable=True),
        sa.Column("profile", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("notify_email", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 2. Documents table
    op.create_table(
        "documents",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("owner_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("source_type", sa.String(16), nullable=False),
        sa.Column("source_uri", sa.Text(), nullable=True),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.String(128), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="uploaded"),
        sa.Column("topic_tree", postgresql.JSONB(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "source_type IN ('upload', 'gdocs')",
            name="ck_documents_source_type",
        ),
        sa.CheckConstraint(
            "status IN ('uploaded', 'parsing', 'parsed', 'generating', 'done', 'failed')",
            name="ck_documents_status",
        ),
    )
    op.create_index("ix_documents_owner_id", "documents", ["owner_id"])

    # 3. Document parts table
    op.create_table(
        "document_parts",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("document_id", sa.UUID(), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("index", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("topic_ids", postgresql.JSONB(), nullable=False),
        sa.Column("source_markdown", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("profile", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(16), nullable=False, server_default="queued"),
        sa.Column("content", postgresql.JSONB(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stage_changed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("document_id", "index", name="uq_document_parts_document_id_index"),
        sa.CheckConstraint(
            "status IN ('queued', 'main_pass', 'resolving', 'assembling', 'published', 'failed')",
            name="ck_document_parts_status",
        ),
    )
    op.create_index(
        "ix_document_parts_status_stage_changed_at",
        "document_parts",
        ["status", "stage_changed_at"],
    )

    # 4. Images table
    op.create_table(
        "images",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("document_id", sa.UUID(), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("topic_id", sa.String(64), nullable=True),
    )
    op.create_index("ix_images_document_id", "images", ["document_id"])

    # 5. User materials (access rights) table
    op.create_table(
        "user_materials",
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("document_id", sa.UUID(), sa.ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("shared_by", sa.UUID(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("role IN ('owner', 'shared')", name="ck_user_materials_role"),
    )

    # 6. Primitives catalog table
    op.create_table(
        "primitives",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("modes", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("params_schema", postgresql.JSONB(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 7. Widgets table
    op.create_table(
        "widgets",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("primitive_id", sa.Text(), sa.ForeignKey("primitives.id", ondelete="SET NULL"), nullable=True),
        sa.Column("mode", sa.String(32), nullable=True),
        sa.Column("params", postgresql.JSONB(), nullable=True),
        sa.Column("source_tsx", sa.Text(), nullable=True),
        sa.Column("compiled_js", sa.Text(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("canonical_id", sa.UUID(), sa.ForeignKey("widgets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_from_part_id",
            sa.UUID(),
            sa.ForeignKey("document_parts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("kind IN ('config', 'code')", name="ck_widgets_kind"),
        sa.CheckConstraint("status IN ('active', 'excluded')", name="ck_widgets_status"),
        sa.CheckConstraint(
            "(kind = 'config' AND primitive_id IS NOT NULL AND mode IS NOT NULL AND params IS NOT NULL) OR "
            "(kind = 'code' AND source_tsx IS NOT NULL AND compiled_js IS NOT NULL)",
            name="ck_widgets_kind_fields",
        ),
    )

    # 8. Widget descriptions table (pgvector 1024 + HNSW)
    op.create_table(
        "widget_descriptions",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("widget_id", sa.UUID(), sa.ForeignKey("widgets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("is_paraphrase", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("embedding", Vector(1024), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_widget_descriptions_widget_id", "widget_descriptions", ["widget_id"])
    op.create_index(
        "ix_widget_descriptions_embedding_hnsw",
        "widget_descriptions",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 128},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )

    # 9. Widget usages table
    op.create_table(
        "widget_usages",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("part_id", sa.UUID(), sa.ForeignKey("document_parts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("widget_id", sa.UUID(), sa.ForeignKey("widgets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("directive_ref", sa.String(64), nullable=False),
        sa.Column("params", postgresql.JSONB(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("part_id", "directive_ref", name="uq_widget_usages_part_id_directive_ref"),
        sa.CheckConstraint("status IN ('ready', 'pending', 'fallback')", name="ck_widget_usages_status"),
    )

    # 10. Widget reports table
    op.create_table(
        "reports",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("widget_id", sa.UUID(), sa.ForeignKey("widgets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("part_id", sa.UUID(), sa.ForeignKey("document_parts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reason", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("widget_id", "user_id", name="uq_reports_widget_id_user_id"),
        sa.CheckConstraint("reason IN ('wrong', 'broken', 'other')", name="ck_reports_reason"),
    )

    # 11. Quiz attempts table
    op.create_table(
        "quiz_attempts",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("part_id", sa.UUID(), sa.ForeignKey("document_parts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("quiz_key", sa.String(12), nullable=False),
        sa.Column("answer", postgresql.JSONB(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_quiz_attempts_user_id_part_id", "quiz_attempts", ["user_id", "part_id"])

    # 12. Quota ledger table
    op.create_table(
        "generation_ledger",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_id", sa.UUID(), sa.ForeignKey("documents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("part_id", sa.UUID(), sa.ForeignKey("document_parts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("op", sa.String(8), nullable=False),
        sa.Column("delta", sa.Integer(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("op IN ('reserve', 'charge', 'refund')", name="ck_generation_ledger_op"),
    )
    op.create_index(
        "ix_generation_ledger_user_id_period_start",
        "generation_ledger",
        ["user_id", "period_start"],
    )
    op.create_index(
        "uq_generation_ledger_part_id_op",
        "generation_ledger",
        ["part_id", "op"],
        unique=True,
        postgresql_where=sa.text("part_id IS NOT NULL"),
    )


def downgrade() -> None:
    # Tables are dropped strictly in reverse dependency order
    op.drop_table("generation_ledger")
    op.drop_table("quiz_attempts")
    op.drop_table("reports")
    op.drop_table("widget_usages")
    op.drop_index("ix_widget_descriptions_embedding_hnsw", table_name="widget_descriptions")
    op.drop_table("widget_descriptions")
    op.drop_table("widgets")
    op.drop_table("primitives")
    op.drop_table("user_materials")
    op.drop_table("images")
    op.drop_table("document_parts")
    op.drop_table("documents")
    op.drop_table("users")
    # Extensions are intentionally kept after downgrade.
