"""field-level review notes, and fests whose dates are not fixed yet

Revision ID: 0015
Revises: 0014
"""
from alembic import op
import sqlalchemy as sa

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("fests", sa.Column("review_fields", sa.JSON(), nullable=True))
    op.add_column("fests", sa.Column("dates_tba", sa.Boolean(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("fests", "dates_tba")
    op.drop_column("fests", "review_fields")
