"""duty roster: shifts and who is on them

Revision ID: 0031
Revises: 0030
"""
from alembic import op
import sqlalchemy as sa

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shifts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("fest_id", sa.Integer(), sa.ForeignKey("fests.id"), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id", name="fk_shift_event"), nullable=True),
        sa.Column("committee_team_id", sa.Integer(), sa.ForeignKey("committee_teams.id", name="fk_shift_team"), nullable=True),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("starts_at", sa.DateTime(), nullable=False),
        sa.Column("ends_at", sa.DateTime(), nullable=False),
        sa.Column("needed", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("open_signup", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", name="fk_shift_creator"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_shifts_fest_id", "shifts", ["fest_id"])
    op.create_table(
        "shift_assignments",
        sa.Column("shift_id", sa.Integer(), sa.ForeignKey("shifts.id"), primary_key=True),
        sa.Column("member_id", sa.Integer(), sa.ForeignKey("fest_members.id"), primary_key=True),
        sa.Column("arrived_at", sa.DateTime(), nullable=True),
        sa.Column("no_show", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("shift_assignments")
    op.drop_index("ix_shifts_fest_id", table_name="shifts")
    op.drop_table("shifts")
