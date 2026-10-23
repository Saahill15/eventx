"""custom short links for fests (and later events)

Revision ID: 0011
Revises: 0010
"""
from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "short_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=40), nullable=False),
        sa.Column("target_type", sa.String(length=10), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("target_type", "target_id", name="uq_short_link_target"),
    )
    op.create_index("ix_short_links_name", "short_links", ["name"], unique=True)
    op.create_index("ix_short_links_id", "short_links", ["id"])


def downgrade() -> None:
    op.drop_index("ix_short_links_id", table_name="short_links")
    op.drop_index("ix_short_links_name", table_name="short_links")
    op.drop_table("short_links")
