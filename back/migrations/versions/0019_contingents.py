"""contingents: visiting colleges, their leaders, assistants and rosters, with per-fest settings

Revision ID: 0019
Revises: 0018
"""
from alembic import op
import sqlalchemy as sa

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "contingent_settings",
        sa.Column("fest_id", sa.Integer(), sa.ForeignKey("fests.id"), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("term", sa.String(length=40), nullable=False, server_default="Contingent"),
        sa.Column("leader_term", sa.String(length=60), nullable=False, server_default="Contingent Leader"),
        sa.Column("assistant_term", sa.String(length=60), nullable=False, server_default="Assistant Contingent Leader"),
        sa.Column("max_assistants", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("min_members", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("max_members", sa.Integer(), nullable=True),
        sa.Column("allow_multiple_per_college", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("requires_approval", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("opens_on", sa.Date(), nullable=True),
        sa.Column("closes_on", sa.Date(), nullable=True),
        sa.Column("lock_roster_after_close", sa.Boolean(), nullable=False, server_default="1"),
    )
    op.create_table(
        "contingents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("fest_id", sa.Integer(), sa.ForeignKey("fests.id"), nullable=False),
        sa.Column("college_name", sa.String(length=200), nullable=False),
        sa.Column("college_id", sa.Integer(), sa.ForeignKey("colleges.id", name="fk_contingents_college"), nullable=True),
        sa.Column("code", sa.String(length=30), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=12), nullable=False, server_default="pending"),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column("leader_user_id", sa.Integer(), sa.ForeignKey("users.id", name="fk_contingents_leader"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("fest_id", "code", name="uq_contingents_fest_code"),
        sa.UniqueConstraint("fest_id", "name", name="uq_contingents_fest_name"),
    )
    op.create_index("ix_contingents_id", "contingents", ["id"])
    op.create_index("ix_contingents_fest_id", "contingents", ["fest_id"])
    op.create_index("ix_contingents_leader_user_id", "contingents", ["leader_user_id"])
    op.create_table(
        "contingent_assistants",
        sa.Column("contingent_id", sa.Integer(), sa.ForeignKey("contingents.id"), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("added_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "contingent_members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("contingent_id", sa.Integer(), sa.ForeignKey("contingents.id"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=30), nullable=True),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("notes", sa.String(length=300), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_contingent_members_id", "contingent_members", ["id"])
    op.create_index("ix_contingent_members_contingent_id", "contingent_members", ["contingent_id"])


def downgrade() -> None:
    op.drop_table("contingent_members")
    op.drop_table("contingent_assistants")
    op.drop_table("contingents")
    op.drop_table("contingent_settings")
