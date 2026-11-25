"""when registration opens: instant, on a date, or not decided yet

Revision ID: 0021
Revises: 0020
"""
from alembic import op
import sqlalchemy as sa

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Events that already exist were open to register the moment they were published, so they stay open
    with op.batch_alter_table("events") as b:
        b.add_column(sa.Column("registration_mode", sa.String(length=12), nullable=False, server_default="open_now"))
        b.add_column(sa.Column("registration_opens_on", sa.Date(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("events") as b:
        b.drop_column("registration_opens_on")
        b.drop_column("registration_mode")
