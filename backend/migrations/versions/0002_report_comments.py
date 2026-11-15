"""Allow ugly reports and store optional comments.

Revision ID: 0002_report_comments
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_report_comments"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("reports", sa.Column("comment", sa.String(length=500), nullable=True))
    op.drop_constraint("ck_reports_reason", "reports", type_="check")
    op.create_check_constraint("ck_reports_reason", "reports", "reason IN ('wrong', 'broken', 'ugly', 'other')")


def downgrade() -> None:
    op.execute("UPDATE reports SET reason = 'other' WHERE reason = 'ugly'")
    op.drop_constraint("ck_reports_reason", "reports", type_="check")
    op.create_check_constraint("ck_reports_reason", "reports", "reason IN ('wrong', 'broken', 'other')")
    op.drop_column("reports", "comment")
