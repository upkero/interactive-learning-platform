"""Store only the parse error code and keep technical details out of the API.

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
    # Rows written before the rename may hold free text; the new CHECK
    # accepts only known codes, so anything else is dropped instead of
    # failing the migration.
    allowed = ", ".join(f"'{code}'" for code in _ERROR_CODES)
    op.execute(f"UPDATE documents SET error = NULL WHERE error IS NOT NULL AND error NOT IN ({allowed})")
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
