"""online payments: payments, refunds, registration holds, refund rules

Revision ID: 0032
Revises: 0031
"""
from alembic import op
import sqlalchemy as sa

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.String(60), nullable=False),
        sa.Column("fest_id", sa.Integer(), sa.ForeignKey("fests.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", name="fk_payment_user"), nullable=False),
        sa.Column("purpose", sa.String(20), nullable=False),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id", name="fk_payment_event"), nullable=True),
        sa.Column("registration_id", sa.Integer(), nullable=True),
        sa.Column("contingent_id", sa.Integer(), sa.ForeignKey("contingents.id", name="fk_payment_contingent"), nullable=True),
        sa.Column("description", sa.String(200), nullable=True),
        sa.Column("amount_paise", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(12), nullable=False, server_default="created"),
        sa.Column("session_id", sa.String(500), nullable=True),
        sa.Column("gateway_payment_id", sa.String(60), nullable=True),
        sa.Column("method", sa.String(40), nullable=True),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
        sa.Column("applied_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_payments_order_id", "payments", ["order_id"], unique=True)
    op.create_index("ix_payments_fest_id", "payments", ["fest_id"])
    op.create_index("ix_payments_user_id", "payments", ["user_id"])
    op.create_index("ix_payments_registration_id", "payments", ["registration_id"])
    op.create_table(
        "refunds",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("payment_id", sa.Integer(), sa.ForeignKey("payments.id"), nullable=False),
        sa.Column("ref", sa.String(60), nullable=False, unique=True),
        sa.Column("amount_paise", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="pending"),
        sa.Column("reason", sa.String(200), nullable=True),
        sa.Column("note", sa.String(300), nullable=True),
        sa.Column("by_user_id", sa.Integer(), sa.ForeignKey("users.id", name="fk_refund_by"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_refunds_payment_id", "refunds", ["payment_id"])
    with op.batch_alter_table("event_registrations") as b:
        b.add_column(sa.Column("hold_expires_at", sa.DateTime(), nullable=True))
    with op.batch_alter_table("finance_settings") as b:
        b.add_column(sa.Column("refund_on_cancel", sa.Boolean(), nullable=False, server_default="1"))
        b.add_column(sa.Column("refund_cutoff_days", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    with op.batch_alter_table("finance_settings") as b:
        b.drop_column("refund_cutoff_days")
        b.drop_column("refund_on_cancel")
    with op.batch_alter_table("event_registrations") as b:
        b.drop_column("hold_expires_at")
    op.drop_index("ix_refunds_payment_id", table_name="refunds")
    op.drop_table("refunds")
    for name in ("ix_payments_registration_id", "ix_payments_user_id", "ix_payments_fest_id", "ix_payments_order_id"):
        op.drop_index(name, table_name="payments")
    op.drop_table("payments")
