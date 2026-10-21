"""check-in details, event cancellation, student profile fields

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as b:
        b.add_column(sa.Column("college_id", sa.Integer(), nullable=True))
        b.add_column(sa.Column("study_year", sa.Integer(), nullable=True))
        b.create_foreign_key("fk_users_college_id", "colleges", ["college_id"], ["id"])
    with op.batch_alter_table("events") as b:
        b.add_column(sa.Column("cancelled_at", sa.DateTime(), nullable=True))
        b.add_column(sa.Column("cancel_reason", sa.String(length=500), nullable=True))
    with op.batch_alter_table("fest_passes") as b:
        b.add_column(sa.Column("checked_in_at", sa.DateTime(), nullable=True))
        b.add_column(sa.Column("checked_in_by", sa.Integer(), nullable=True))
        b.create_foreign_key("fk_fest_passes_checked_in_by", "users", ["checked_in_by"], ["id"])
    with op.batch_alter_table("event_registrations") as b:
        b.add_column(sa.Column("attended", sa.Boolean(), nullable=False, server_default=sa.false()))
        b.add_column(sa.Column("attended_at", sa.DateTime(), nullable=True))
        b.add_column(sa.Column("attended_by", sa.Integer(), nullable=True))
        b.create_foreign_key("fk_event_registrations_attended_by", "users", ["attended_by"], ["id"])


def downgrade() -> None:
    with op.batch_alter_table("event_registrations") as b:
        b.drop_constraint("fk_event_registrations_attended_by", type_="foreignkey")
        b.drop_column("attended_by")
        b.drop_column("attended_at")
        b.drop_column("attended")
    with op.batch_alter_table("fest_passes") as b:
        b.drop_constraint("fk_fest_passes_checked_in_by", type_="foreignkey")
        b.drop_column("checked_in_by")
        b.drop_column("checked_in_at")
    with op.batch_alter_table("events") as b:
        b.drop_column("cancel_reason")
        b.drop_column("cancelled_at")
    with op.batch_alter_table("users") as b:
        b.drop_constraint("fk_users_college_id", type_="foreignkey")
        b.drop_column("study_year")
        b.drop_column("college_id")
