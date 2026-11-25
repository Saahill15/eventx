"""sponsors and partners of a fest

Revision ID: 0024
Revises: 0023
"""
from alembic import op
import sqlalchemy as sa

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fest_sponsors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("fest_id", sa.Integer(), sa.ForeignKey("fests.id"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("tier_label", sa.String(length=60), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("logo_url", sa.String(length=500), nullable=True),
        sa.Column("website_url", sa.String(length=500), nullable=True),
        sa.Column("blurb", sa.String(length=200), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_fest_sponsors_fest_id", "fest_sponsors", ["fest_id"])
    op.create_index("ix_fest_sponsors_id", "fest_sponsors", ["id"])


def downgrade() -> None:
    op.drop_index("ix_fest_sponsors_id", table_name="fest_sponsors")
    op.drop_index("ix_fest_sponsors_fest_id", table_name="fest_sponsors")
    op.drop_table("fest_sponsors")
