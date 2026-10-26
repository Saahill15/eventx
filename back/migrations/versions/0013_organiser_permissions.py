"""per-organiser permissions for fests and city events

Revision ID: 0013
Revises: 0012
"""
from alembic import op
import sqlalchemy as sa

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as b:
        b.add_column(sa.Column("can_host_fests", sa.Boolean(), nullable=False, server_default="0"))
        b.add_column(sa.Column("can_host_city_events", sa.Boolean(), nullable=False, server_default="0"))
    # Organisers who exist today keep both abilities. Everyone promoted from now on is asked explicitly
    op.execute("UPDATE users SET can_host_fests = 1, can_host_city_events = 1 WHERE role = 'organizer'")


def downgrade() -> None:
    with op.batch_alter_table("users") as b:
        b.drop_column("can_host_city_events")
        b.drop_column("can_host_fests")
