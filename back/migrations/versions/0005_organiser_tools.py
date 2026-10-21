"""college partnership, fest details and review, event extras, media, custom questions, announcements

Revision ID: 0005
Revises: 0004
"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("colleges") as b:
        b.add_column(sa.Column("partner_status", sa.String(length=20), nullable=False, server_default="prospect"))
        b.add_column(sa.Column("coordinator_name", sa.String(length=255), nullable=True))
        b.add_column(sa.Column("coordinator_phone", sa.String(length=30), nullable=True))
        b.add_column(sa.Column("coordinator_email", sa.String(length=255), nullable=True))
        b.add_column(sa.Column("partner_since", sa.Date(), nullable=True))
        b.add_column(sa.Column("partner_notes", sa.Text(), nullable=True))
    # Colleges that already exist were added by an admin deliberately: treat them as partners
    op.execute("UPDATE colleges SET partner_status = 'partner'")

    with op.batch_alter_table("fests") as b:
        b.add_column(sa.Column("description", sa.Text(), nullable=True))
        b.add_column(sa.Column("start_date", sa.Date(), nullable=True))
        b.add_column(sa.Column("end_date", sa.Date(), nullable=True))
        b.add_column(sa.Column("campus_address", sa.String(length=500), nullable=True))
        b.add_column(sa.Column("map_url", sa.String(length=500), nullable=True))
        b.add_column(sa.Column("instagram_url", sa.String(length=500), nullable=True))
        b.add_column(sa.Column("website_url", sa.String(length=500), nullable=True))
        b.add_column(sa.Column("extra_sections", sa.JSON(), nullable=True))
        b.add_column(sa.Column("contact_name", sa.String(length=255), nullable=True))
        b.add_column(sa.Column("contact_email", sa.String(length=255), nullable=True))
        b.add_column(sa.Column("contact_phone", sa.String(length=30), nullable=True))
        b.add_column(sa.Column("faculty_name", sa.String(length=255), nullable=True))
        b.add_column(sa.Column("faculty_phone", sa.String(length=30), nullable=True))
        b.add_column(sa.Column("faculty_email", sa.String(length=255), nullable=True))
        b.add_column(sa.Column("review_status", sa.String(length=20), nullable=False, server_default="draft"))
        b.add_column(sa.Column("review_note", sa.String(length=1000), nullable=True))
        b.add_column(sa.Column("submitted_at", sa.DateTime(), nullable=True))
        b.add_column(sa.Column("reviewed_by", sa.Integer(), nullable=True))
        b.add_column(sa.Column("reviewed_at", sa.DateTime(), nullable=True))
        b.create_foreign_key("fk_fests_reviewed_by", "users", ["reviewed_by"], ["id"])
    # Fests that are already live were accepted before reviews existed
    op.execute("UPDATE fests SET review_status = 'approved' WHERE status = 'live'")

    with op.batch_alter_table("events") as b:
        b.add_column(sa.Column("end_time", sa.String(length=50), nullable=True))
        b.add_column(sa.Column("extra_sections", sa.JSON(), nullable=True))

    op.create_table(
        "organizer_colleges",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("college_id", sa.Integer(), sa.ForeignKey("colleges.id"), primary_key=True),
    )
    op.create_table(
        "media",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("mime", sa.String(length=100), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_media_owner_id", "media", ["owner_id"])
    op.create_table(
        "event_questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("options", sa.JSON(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_event_questions_id", "event_questions", ["id"])
    op.create_index("ix_event_questions_event_id", "event_questions", ["event_id"])
    op.create_table(
        "registration_answers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("registration_id", sa.Integer(), sa.ForeignKey("event_registrations.id"), nullable=False),
        sa.Column("question_id", sa.Integer(), sa.ForeignKey("event_questions.id"), nullable=False),
        sa.Column("answer", sa.String(length=500), nullable=False),
    )
    op.create_index("ix_registration_answers_id", "registration_answers", ["id"])
    op.create_index("ix_registration_answers_registration_id", "registration_answers", ["registration_id"])
    op.create_table(
        "announcements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("fest_id", sa.Integer(), sa.ForeignKey("fests.id"), nullable=False),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id"), nullable=True),
        sa.Column("author_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("body", sa.String(length=2000), nullable=False),
        sa.Column("email_requested", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("emails_sent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("emails_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_announcements_id", "announcements", ["id"])
    op.create_index("ix_announcements_fest_id", "announcements", ["fest_id"])


def downgrade() -> None:
    op.drop_table("announcements")
    op.drop_table("registration_answers")
    op.drop_table("event_questions")
    op.drop_table("media")
    op.drop_table("organizer_colleges")
    with op.batch_alter_table("events") as b:
        b.drop_column("extra_sections")
        b.drop_column("end_time")
    with op.batch_alter_table("fests") as b:
        b.drop_constraint("fk_fests_reviewed_by", type_="foreignkey")
        for col in ("reviewed_at", "reviewed_by", "submitted_at", "review_note", "review_status", "faculty_email", "faculty_phone",
                    "faculty_name", "contact_phone", "contact_email", "contact_name", "extra_sections", "website_url", "instagram_url",
                    "map_url", "campus_address", "end_date", "start_date", "description"):
            b.drop_column(col)
    with op.batch_alter_table("colleges") as b:
        for col in ("partner_notes", "partner_since", "coordinator_email", "coordinator_phone", "coordinator_name", "partner_status"):
            b.drop_column(col)
