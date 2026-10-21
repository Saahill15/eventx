"""student verification, students-only events, student pricing

Revision ID: 0004
Revises: 0003
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as b:
        b.add_column(sa.Column("student_verified_until", sa.DateTime(), nullable=True))
    with op.batch_alter_table("colleges") as b:
        b.add_column(sa.Column("email_domains", sa.String(length=500), nullable=True))
    with op.batch_alter_table("events") as b:
        b.add_column(sa.Column("students_only", sa.Boolean(), nullable=False, server_default=sa.false()))
        b.add_column(sa.Column("student_price", sa.Float(), nullable=True))
    with op.batch_alter_table("event_registrations") as b:
        b.add_column(sa.Column("amount_due", sa.Float(), nullable=True))
    op.create_table(
        "student_verifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("method", sa.Enum("email", "proof", name="verificationmethodenum"), nullable=False),
        sa.Column("status", sa.Enum("pending", "approved", "rejected", name="verificationstatusenum"), nullable=False),
        sa.Column("college_id", sa.Integer(), sa.ForeignKey("colleges.id"), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("code_hash", sa.String(length=128), nullable=True),
        sa.Column("code_expires_at", sa.DateTime(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("document_type", sa.String(length=30), nullable=True),
        sa.Column("document_name", sa.String(length=255), nullable=True),
        sa.Column("document_mime", sa.String(length=100), nullable=True),
        sa.Column("document_data", sa.LargeBinary(), nullable=True),
        sa.Column("reject_reason", sa.String(length=500), nullable=True),
        sa.Column("reviewed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_student_verifications_id", "student_verifications", ["id"])
    op.create_index("ix_student_verifications_user_id", "student_verifications", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_student_verifications_user_id", table_name="student_verifications")
    op.drop_index("ix_student_verifications_id", table_name="student_verifications")
    op.drop_table("student_verifications")
    with op.batch_alter_table("event_registrations") as b:
        b.drop_column("amount_due")
    with op.batch_alter_table("events") as b:
        b.drop_column("student_price")
        b.drop_column("students_only")
    with op.batch_alter_table("colleges") as b:
        b.drop_column("email_domains")
    with op.batch_alter_table("users") as b:
        b.drop_column("student_verified_until")
