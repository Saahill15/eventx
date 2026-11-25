"""event span, coordinator and registration deadline

Revision ID: 0020
Revises: 0019
"""
from alembic import op
import sqlalchemy as sa

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("events") as b:
        b.add_column(sa.Column("span_days", sa.Integer(), nullable=False, server_default="1"))
        b.add_column(sa.Column("coordinator_name", sa.String(length=120), nullable=True))
        b.add_column(sa.Column("coordinator_phone", sa.String(length=30), nullable=True))
        b.add_column(sa.Column("registration_deadline", sa.Date(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("events") as b:
        b.drop_column("registration_deadline")
        b.drop_column("coordinator_phone")
        b.drop_column("coordinator_name")
        b.drop_column("span_days")
