"""committee meetings with agenda, minutes, attendance and action items

Revision ID: 0018
Revises: 0017
"""
from alembic import op
import sqlalchemy as sa

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fest_meetings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("fest_id", sa.Integer(), sa.ForeignKey("fests.id"), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("starts_at", sa.DateTime(), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("agenda", sa.Text(), nullable=True),
        sa.Column("minutes", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", name="fk_fest_meetings_creator"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_fest_meetings_id", "fest_meetings", ["id"])
    op.create_index("ix_fest_meetings_fest_id", "fest_meetings", ["fest_id"])
    op.create_table(
        "fest_meeting_attendees",
        sa.Column("meeting_id", sa.Integer(), sa.ForeignKey("fest_meetings.id"), primary_key=True),
        sa.Column("member_id", sa.Integer(), sa.ForeignKey("fest_members.id"), primary_key=True),
        sa.Column("attended", sa.Boolean(), nullable=False, server_default="0"),
    )
    with op.batch_alter_table("fest_tasks") as b:
        b.add_column(sa.Column("meeting_id", sa.Integer(), nullable=True))
        b.create_foreign_key("fk_fest_tasks_meeting", "fest_meetings", ["meeting_id"], ["id"])


def downgrade() -> None:
    with op.batch_alter_table("fest_tasks") as b:
        b.drop_constraint("fk_fest_tasks_meeting", type_="foreignkey")
        b.drop_column("meeting_id")
    op.drop_table("fest_meeting_attendees")
    op.drop_index("ix_fest_meetings_fest_id", table_name="fest_meetings")
    op.drop_index("ix_fest_meetings_id", table_name="fest_meetings")
    op.drop_table("fest_meetings")
