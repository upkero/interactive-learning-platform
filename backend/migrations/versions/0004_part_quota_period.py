"""Keep each part's reservation period.

Revision ID: 0004_part_quota_period
Revises: 0003_document_error_code
"""

import sqlalchemy as sa
from alembic import op

revision = "0004_part_quota_period"
down_revision = "0003_document_error_code"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("document_parts", sa.Column("quota_period_start", sa.Date(), nullable=True))
    op.execute("""
        UPDATE document_parts AS part
        SET quota_period_start = (
            SELECT ledger.period_start FROM generation_ledger AS ledger
            WHERE ledger.document_id = part.document_id AND ledger.op = 'reserve'
            ORDER BY ledger.id DESC LIMIT 1
        )
    """)


def downgrade() -> None:
    op.drop_column("document_parts", "quota_period_start")
