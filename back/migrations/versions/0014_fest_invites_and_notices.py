"""fest team invitations that must be accepted, and account notices

Revision ID: 0014
Revises: 0013
"""
from alembic import op
import sqlalchemy as sa

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fest_invites",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("fest_id", sa.Integer(), sa.ForeignKey("fests.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("invited_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role", sa.String(length=12), nullable=False),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_fest_invites_id", "fest_invites", ["id"])
    op.create_index("ix_fest_invites_fest_id", "fest_invites", ["fest_id"])
    op.create_index("ix_fest_invites_user_id", "fest_invites", ["user_id"])

    op.create_table(
        "account_notices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("body", sa.String(length=500), nullable=False),
        sa.Column("invite_id", sa.Integer(), sa.ForeignKey("fest_invites.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("read_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_account_notices_id", "account_notices", ["id"])
    op.create_index("ix_account_notices_user_id", "account_notices", ["user_id"])


def downgrade() -> None:
    op.drop_table("account_notices")
    op.drop_table("fest_invites")
