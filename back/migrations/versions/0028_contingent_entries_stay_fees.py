"""contingents in events, accommodation and fees

Revision ID: 0028
Revises: 0027
"""
from alembic import op
import sqlalchemy as sa

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def _id():
    return sa.Column("id", sa.Integer(), primary_key=True)


def _now():
    return sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now())


def upgrade() -> None:
    with op.batch_alter_table("events") as b:
        b.add_column(sa.Column("contingent_entries", sa.Boolean(), nullable=False, server_default="0"))
        b.add_column(sa.Column("entries_per_contingent", sa.Integer(), nullable=False, server_default="1"))
        b.add_column(sa.Column("entry_fee_paise", sa.Integer(), nullable=False, server_default="0"))
        b.add_column(sa.Column("entry_fee_per", sa.String(12), nullable=False, server_default="entry"))
        b.add_column(sa.Column("entry_deadline", sa.Date(), nullable=True))
    with op.batch_alter_table("contingent_settings") as b:
        b.add_column(sa.Column("registration_fee_paise", sa.Integer(), nullable=False, server_default="0"))
        b.add_column(sa.Column("fee_per_member_paise", sa.Integer(), nullable=False, server_default="0"))
        b.add_column(sa.Column("fee_instructions", sa.String(1000), nullable=True))
        b.add_column(sa.Column("fees_due_on", sa.Date(), nullable=True))
        b.add_column(sa.Column("accommodation_enabled", sa.Boolean(), nullable=False, server_default="0"))
        b.add_column(sa.Column("accommodation_closes_on", sa.Date(), nullable=True))

    op.create_table(
        "contingent_entries", _id(),
        sa.Column("fest_id", sa.Integer(), sa.ForeignKey("fests.id"), nullable=False),
        sa.Column("contingent_id", sa.Integer(), sa.ForeignKey("contingents.id", name="fk_entry_contingent"), nullable=False),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id", name="fk_entry_event"), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="confirmed"),
        sa.Column("note", sa.String(300), nullable=True),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", name="fk_entry_creator"), nullable=True),
        _now(),
    )
    for col in ("fest_id", "contingent_id", "event_id"):
        op.create_index(f"ix_contingent_entries_{col}", "contingent_entries", [col])
    op.create_table(
        "contingent_entry_members",
        sa.Column("entry_id", sa.Integer(), sa.ForeignKey("contingent_entries.id"), primary_key=True),
        sa.Column("member_id", sa.Integer(), sa.ForeignKey("contingent_members.id", name="fk_entry_member"), primary_key=True),
    )
    op.create_table(
        "accommodation_options", _id(),
        sa.Column("fest_id", sa.Integer(), sa.ForeignKey("fests.id"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("gender_policy", sa.String(8), nullable=False, server_default="any"),
        sa.Column("fee_per_night_paise", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_accommodation_options_fest_id", "accommodation_options", ["fest_id"])
    op.create_table(
        "accommodation_requests", _id(),
        sa.Column("fest_id", sa.Integer(), sa.ForeignKey("fests.id"), nullable=False),
        sa.Column("contingent_id", sa.Integer(), sa.ForeignKey("contingents.id", name="fk_stay_contingent"), nullable=False, unique=True),
        sa.Column("boys", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("girls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("others", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("arrival_date", sa.Date(), nullable=False),
        sa.Column("departure_date", sa.Date(), nullable=False),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column("status", sa.String(10), nullable=False, server_default="requested"),
        sa.Column("decision_note", sa.String(300), nullable=True),
        sa.Column("decided_by_id", sa.Integer(), sa.ForeignKey("users.id", name="fk_stay_decider"), nullable=True),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        _now(),
    )
    op.create_index("ix_accommodation_requests_fest_id", "accommodation_requests", ["fest_id"])
    op.create_table(
        "accommodation_allocations", _id(),
        sa.Column("request_id", sa.Integer(), sa.ForeignKey("accommodation_requests.id"), nullable=False),
        sa.Column("option_id", sa.Integer(), sa.ForeignKey("accommodation_options.id", name="fk_stay_alloc_option"), nullable=False),
        sa.Column("grp", sa.String(8), nullable=False),
        sa.Column("people", sa.Integer(), nullable=False),
        sa.UniqueConstraint("request_id", "option_id", "grp", name="uq_stay_allocation"),
    )
    op.create_index("ix_accommodation_allocations_request_id", "accommodation_allocations", ["request_id"])
    op.create_index("ix_accommodation_allocations_option_id", "accommodation_allocations", ["option_id"])
    op.create_table(
        "fee_adjustments", _id(),
        sa.Column("fest_id", sa.Integer(), sa.ForeignKey("fests.id"), nullable=False),
        sa.Column("contingent_id", sa.Integer(), sa.ForeignKey("contingents.id", name="fk_fee_adj_contingent"), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("amount_paise", sa.Integer(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", name="fk_fee_adj_creator"), nullable=True),
        _now(),
    )
    op.create_index("ix_fee_adjustments_fest_id", "fee_adjustments", ["fest_id"])
    op.create_index("ix_fee_adjustments_contingent_id", "fee_adjustments", ["contingent_id"])
    op.create_table(
        "fee_payments", _id(),
        sa.Column("fest_id", sa.Integer(), sa.ForeignKey("fests.id"), nullable=False),
        sa.Column("contingent_id", sa.Integer(), sa.ForeignKey("contingents.id", name="fk_fee_pay_contingent"), nullable=False),
        sa.Column("amount_paise", sa.Integer(), nullable=False),
        sa.Column("received_on", sa.Date(), nullable=False),
        sa.Column("method", sa.String(40), nullable=True),
        sa.Column("reference", sa.String(100), nullable=True),
        sa.Column("note", sa.String(200), nullable=True),
        sa.Column("recorded_by_id", sa.Integer(), sa.ForeignKey("users.id", name="fk_fee_pay_recorder"), nullable=True),
        _now(),
    )
    op.create_index("ix_fee_payments_fest_id", "fee_payments", ["fest_id"])
    op.create_index("ix_fee_payments_contingent_id", "fee_payments", ["contingent_id"])


def downgrade() -> None:
    for t in ("fee_payments", "fee_adjustments", "accommodation_allocations", "accommodation_requests", "accommodation_options", "contingent_entry_members", "contingent_entries"):
        op.drop_table(t)
    with op.batch_alter_table("contingent_settings") as b:
        for c in ("accommodation_closes_on", "accommodation_enabled", "fees_due_on", "fee_instructions", "fee_per_member_paise", "registration_fee_paise"):
            b.drop_column(c)
    with op.batch_alter_table("events") as b:
        for c in ("entry_deadline", "entry_fee_per", "entry_fee_paise", "entries_per_contingent", "contingent_entries"):
            b.drop_column(c)
