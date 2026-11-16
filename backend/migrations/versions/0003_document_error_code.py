"""Store the public parse error code separately from technical details.

Revision ID: 0003_document_error_code
Revises: 0002_report_comments
"""

import sqlalchemy as sa
from alembic import op

revision = "0003_document_error_code"
down_revision = "0002_report_comments"
branch_labels = None
depends_on = None

_ERROR_CODES = (
    "parse_failed",
    "gdocs_not_public",
    "gdocs_import_failed",
    "too_many_pages",
    "empty_document",
    "enqueue_failed",
)


def upgrade() -> None:
    # Preserve old free-text failures before applying the code-only CHECK.
    allowed = ", ".join(f"'{code}'" for code in _ERROR_CODES)
    op.add_column("documents", sa.Column("error_detail", sa.Text(), nullable=True))
    op.execute(f"UPDATE documents SET error_detail = error WHERE error IS NOT NULL AND error NOT IN ({allowed})")
    op.execute(f"UPDATE documents SET error = 'parse_failed' WHERE error IS NOT NULL AND error NOT IN ({allowed})")
    op.alter_column(
        "documents",
        "error",
        new_column_name="error_code",
        existing_type=sa.Text(),
        type_=sa.String(length=64),
        existing_nullable=True,
    )
    op.create_check_constraint(
        "ck_documents_error_code",
        "documents",
        f"error_code IS NULL OR error_code IN ({allowed})",
    )


def downgrade() -> None:
    op.drop_constraint("ck_documents_error_code", "documents", type_="check")
    op.alter_column(
        "documents",
        "error_code",
        new_column_name="error",
        existing_type=sa.String(length=64),
        type_=sa.Text(),
        existing_nullable=True,
    )
    # The old column can store either a code or details. Prefer the
    # diagnostic text where present rather than silently discarding it.
    op.execute("UPDATE documents SET error = error_detail WHERE error_detail IS NOT NULL")
    op.drop_column("documents", "error_detail")
