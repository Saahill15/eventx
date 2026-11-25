"""finance: categories, budget, expenses with approvals, income and sponsorship money

Revision ID: 0027
Revises: 0026
"""
from alembic import op
import sqlalchemy as sa

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def _id():
    return sa.Column("id", sa.Integer(), primary_key=True)


def _now():
    return sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now())


def upgrade() -> None:
    op.create_table(
        "finance_settings",
        sa.Column("fest_id", sa.Integer(), sa.ForeignKey("fests.id"), primary_key=True),
        sa.Column("auto_approve_below_paise", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("receipt_required_above_paise", sa.Integer(), nullable=True),
    )
    op.create_table(
        "finance_categories", _id(),
        sa.Column("fest_id", sa.Integer(), sa.ForeignKey("fests.id"), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("kind", sa.String(8), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("fest_id", "name", name="uq_finance_category_fest_name"),
    )
    op.create_index("ix_finance_categories_fest_id", "finance_categories", ["fest_id"])
    op.create_table(
        "budget_lines", _id(),
        sa.Column("fest_id", sa.Integer(), sa.ForeignKey("fests.id"), nullable=False),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("finance_categories.id", name="fk_budget_line_category"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("planned_paise", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("committee_team_id", sa.Integer(), sa.ForeignKey("committee_teams.id", name="fk_budget_line_team"), nullable=True),
        sa.Column("notes", sa.String(500), nullable=True),
        _now(),
    )
    op.create_index("ix_budget_lines_fest_id", "budget_lines", ["fest_id"])
    op.create_table(
        "expenses", _id(),
        sa.Column("fest_id", sa.Integer(), sa.ForeignKey("fests.id"), nullable=False),
        sa.Column("budget_line_id", sa.Integer(), sa.ForeignKey("budget_lines.id", name="fk_expense_budget_line"), nullable=True),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("finance_categories.id", name="fk_expense_category"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("amount_paise", sa.Integer(), nullable=False),
        sa.Column("spent_on", sa.Date(), nullable=False),
        sa.Column("vendor", sa.String(120), nullable=True),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column("receipts", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(10), nullable=False, server_default="pending"),
        sa.Column("requested_by_id", sa.Integer(), sa.ForeignKey("users.id", name="fk_expense_requester"), nullable=False),
        sa.Column("paid_by_member_id", sa.Integer(), sa.ForeignKey("fest_members.id", name="fk_expense_paid_by"), nullable=True),
        sa.Column("decided_by_id", sa.Integer(), sa.ForeignKey("users.id", name="fk_expense_decider"), nullable=True),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.Column("decision_note", sa.String(300), nullable=True),
        sa.Column("paid_on", sa.Date(), nullable=True),
        sa.Column("paid_note", sa.String(200), nullable=True),
        _now(),
    )
    op.create_index("ix_expenses_fest_id", "expenses", ["fest_id"])
    op.create_index("ix_expenses_budget_line_id", "expenses", ["budget_line_id"])
    op.create_table(
        "income_items", _id(),
        sa.Column("fest_id", sa.Integer(), sa.ForeignKey("fests.id"), nullable=False),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("finance_categories.id", name="fk_income_category"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("source", sa.String(120), nullable=True),
        sa.Column("sponsor_id", sa.Integer(), sa.ForeignKey("fest_sponsors.id", name="fk_income_sponsor"), nullable=True),
        sa.Column("expected_paise", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("due_on", sa.Date(), nullable=True),
        sa.Column("notes", sa.String(500), nullable=True),
        _now(),
    )
    op.create_index("ix_income_items_fest_id", "income_items", ["fest_id"])
    op.create_table(
        "income_payments", _id(),
        sa.Column("income_id", sa.Integer(), sa.ForeignKey("income_items.id"), nullable=False),
        sa.Column("amount_paise", sa.Integer(), nullable=False),
        sa.Column("received_on", sa.Date(), nullable=False),
        sa.Column("method", sa.String(40), nullable=True),
        sa.Column("note", sa.String(200), nullable=True),
        sa.Column("recorded_by_id", sa.Integer(), sa.ForeignKey("users.id", name="fk_income_payment_recorder"), nullable=True),
        _now(),
    )
    op.create_index("ix_income_payments_income_id", "income_payments", ["income_id"])


def downgrade() -> None:
    for t in ("income_payments", "income_items", "expenses", "budget_lines", "finance_categories", "finance_settings"):
        op.drop_table(t)
