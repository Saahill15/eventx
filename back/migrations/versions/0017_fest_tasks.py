"""committee tasks

Revision ID: 0017
Revises: 0016
"""
from alembic import op
import sqlalchemy as sa

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fest_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("fest_id", sa.Integer(), sa.ForeignKey("fests.id"), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=10), nullable=False, server_default="todo"),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("assignee_member_id", sa.Integer(), sa.ForeignKey("fest_members.id", name="fk_fest_tasks_assignee"), nullable=True),
        sa.Column("committee_team_id", sa.Integer(), sa.ForeignKey("committee_teams.id", name="fk_fest_tasks_team"), nullable=True),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", name="fk_fest_tasks_creator"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_fest_tasks_id", "fest_tasks", ["id"])
    op.create_index("ix_fest_tasks_fest_id", "fest_tasks", ["fest_id"])


def downgrade() -> None:
    op.drop_index("ix_fest_tasks_fest_id", table_name="fest_tasks")
    op.drop_index("ix_fest_tasks_id", table_name="fest_tasks")
    op.drop_table("fest_tasks")
