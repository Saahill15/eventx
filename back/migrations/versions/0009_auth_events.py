"""sign-in attempt log

Revision ID: 0009
Revises: 0008
"""
from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auth_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("at", sa.DateTime(), nullable=False),
        sa.Column("portal", sa.String(length=10), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.String(length=60), nullable=False),
    )
    op.create_index("ix_auth_events_at", "auth_events", ["at"])
    op.create_index("ix_auth_events_id", "auth_events", ["id"])


def downgrade() -> None:
    op.drop_index("ix_auth_events_id", table_name="auth_events")
    op.drop_index("ix_auth_events_at", table_name="auth_events")
    op.drop_table("auth_events")
