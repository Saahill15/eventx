"""ticketing: tiers, promo codes, waitlist, certificates

Revision ID: 0029
Revises: 0028
"""
from alembic import op
import sqlalchemy as sa

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def _id():
    return sa.Column("id", sa.Integer(), primary_key=True)


def _now():
    return sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now())


def upgrade() -> None:
    op.create_table(
        "ticket_tiers", _id(),
        sa.Column("fest_id", sa.Integer(), sa.ForeignKey("fests.id"), nullable=False),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id", name="fk_tier_event"), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("description", sa.String(300), nullable=True),
        sa.Column("price_paise", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("student_price_paise", sa.Integer(), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=True),
        sa.Column("sales_open_on", sa.Date(), nullable=True),
        sa.Column("sales_close_on", sa.Date(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="1"),
        _now(),
    )
    op.create_index("ix_ticket_tiers_fest_id", "ticket_tiers", ["fest_id"])
    op.create_index("ix_ticket_tiers_event_id", "ticket_tiers", ["event_id"])
    op.create_table(
        "promo_codes", _id(),
        sa.Column("fest_id", sa.Integer(), sa.ForeignKey("fests.id"), nullable=False),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("description", sa.String(200), nullable=True),
        sa.Column("kind", sa.String(8), nullable=False),
        sa.Column("value", sa.Integer(), nullable=False),
        sa.Column("event_ids", sa.JSON(), nullable=True),
        sa.Column("max_uses", sa.Integer(), nullable=True),
        sa.Column("per_user_limit", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("students_only", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="1"),
        _now(),
        sa.UniqueConstraint("fest_id", "code", name="uq_promo_fest_code"),
    )
    op.create_index("ix_promo_codes_fest_id", "promo_codes", ["fest_id"])

    with op.batch_alter_table("events") as b:
        b.add_column(sa.Column("waitlist_enabled", sa.Boolean(), nullable=False, server_default="0"))
        b.add_column(sa.Column("waitlist_limit", sa.Integer(), nullable=True))
    with op.batch_alter_table("event_registrations") as b:
        b.add_column(sa.Column("ticket_tier_id", sa.Integer(), nullable=True))
        b.add_column(sa.Column("promo_code_id", sa.Integer(), nullable=True))
        b.add_column(sa.Column("discount_paise", sa.Integer(), nullable=False, server_default="0"))
        b.create_foreign_key("fk_registration_tier", "ticket_tiers", ["ticket_tier_id"], ["id"])
        b.create_foreign_key("fk_registration_promo", "promo_codes", ["promo_code_id"], ["id"])
        b.create_index("ix_event_registrations_ticket_tier_id", ["ticket_tier_id"])
        b.create_index("ix_event_registrations_promo_code_id", ["promo_code_id"])

    op.create_table(
        "waitlist_entries", _id(),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id", name="fk_waitlist_event"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", name="fk_waitlist_user"), nullable=False),
        sa.Column("ticket_tier_id", sa.Integer(), sa.ForeignKey("ticket_tiers.id", name="fk_waitlist_tier"), nullable=True),
        sa.Column("promo_code", sa.String(40), nullable=True),
        sa.Column("team_name", sa.String(80), nullable=True),
        sa.Column("answers", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(10), nullable=False, server_default="waiting"),
        sa.Column("note", sa.String(300), nullable=True),
        _now(),
        sa.Column("promoted_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_waitlist_entries_event_id", "waitlist_entries", ["event_id"])
    op.create_index("ix_waitlist_entries_user_id", "waitlist_entries", ["user_id"])
    op.create_table(
        "certificate_templates", _id(),
        sa.Column("fest_id", sa.Integer(), sa.ForeignKey("fests.id"), nullable=False),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id", name="fk_cert_template_event"), nullable=True),
        sa.Column("kind", sa.String(16), nullable=False, server_default="participation"),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("body", sa.String(1000), nullable=False),
        sa.Column("signatories", sa.JSON(), nullable=True),
        _now(),
    )
    op.create_index("ix_certificate_templates_fest_id", "certificate_templates", ["fest_id"])
    op.create_table(
        "certificates", _id(),
        sa.Column("fest_id", sa.Integer(), sa.ForeignKey("fests.id"), nullable=False),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id", name="fk_certificate_event"), nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", name="fk_certificate_user"), nullable=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("code", sa.String(12), nullable=False),
        sa.Column("recipient_name", sa.String(120), nullable=False),
        sa.Column("college_name", sa.String(200), nullable=True),
        sa.Column("award_text", sa.String(120), nullable=True),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("body", sa.String(1200), nullable=False),
        sa.Column("signatories", sa.JSON(), nullable=True),
        sa.Column("fest_name", sa.String(255), nullable=False),
        sa.Column("event_title", sa.String(255), nullable=True),
        sa.Column("issued_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("issued_by_id", sa.Integer(), sa.ForeignKey("users.id", name="fk_certificate_issuer"), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_reason", sa.String(200), nullable=True),
    )
    op.create_index("ix_certificates_fest_id", "certificates", ["fest_id"])
    op.create_index("ix_certificates_event_id", "certificates", ["event_id"])
    op.create_index("ix_certificates_user_id", "certificates", ["user_id"])
    op.create_index("ix_certificates_code", "certificates", ["code"], unique=True)


def downgrade() -> None:
    for t in ("certificates", "certificate_templates", "waitlist_entries"):
        op.drop_table(t)
    with op.batch_alter_table("event_registrations") as b:
        b.drop_index("ix_event_registrations_promo_code_id")
        b.drop_index("ix_event_registrations_ticket_tier_id")
        b.drop_constraint("fk_registration_promo", type_="foreignkey")
        b.drop_constraint("fk_registration_tier", type_="foreignkey")
        b.drop_column("discount_paise"); b.drop_column("promo_code_id"); b.drop_column("ticket_tier_id")
    with op.batch_alter_table("events") as b:
        b.drop_column("waitlist_limit"); b.drop_column("waitlist_enabled")
    op.drop_table("promo_codes")
    op.drop_table("ticket_tiers")
