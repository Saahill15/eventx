"""the title an invitation offers (Chairperson, Vice Chairperson...)

Revision ID: 0023
Revises: 0022
"""
from alembic import op
import sqlalchemy as sa

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("fest_invites") as b:
        b.add_column(sa.Column("title", sa.String(length=80), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("fest_invites") as b:
        b.drop_column("title")
