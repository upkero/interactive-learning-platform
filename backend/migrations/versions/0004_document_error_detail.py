"""Add diagnostics where the original revision 0003 was already applied.

Revision ID: 0004_document_error_detail
Revises: 0003_document_error_code
"""

from alembic import op

revision = "0004_document_error_detail"
down_revision = "0003_document_error_code"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Fresh installations receive the column in 0003; installations that
    # already ran the earlier version of 0003 need it added here.
    op.execute("ALTER TABLE documents ADD COLUMN IF NOT EXISTS error_detail TEXT")


def downgrade() -> None:
    # The column belongs to 0003 and must remain until 0003 is downgraded.
    pass
