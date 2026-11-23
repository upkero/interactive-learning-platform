"""Track the current generation's first part index.

Revision ID: 0005_generation_start_index
Revises: 0004_part_quota_period
"""

import sqlalchemy as sa
from alembic import op

revision = "0005_generation_start_index"
down_revision = "0004_part_quota_period"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("generation_start_index", sa.Integer(), server_default="0", nullable=False))


def downgrade() -> None:
    op.drop_column("documents", "generation_start_index")
