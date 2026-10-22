"""organiser welcome notice, reason for rejected city events

Revision ID: 0007
Revises: 0006
"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as b:
        b.add_column(sa.Column("organizer_welcome_pending", sa.Boolean(), nullable=False, server_default="0"))
    with op.batch_alter_table("events") as b:
        b.add_column(sa.Column("reject_reason", sa.String(length=500), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("events") as b:
        b.drop_column("reject_reason")
    with op.batch_alter_table("users") as b:
        b.drop_column("organizer_welcome_pending")
