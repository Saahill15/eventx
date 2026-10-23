"""password resets, Google sign-in, terms acceptance, team events, fest transfers

Revision ID: 0012
Revises: 0011
"""
from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "password_resets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
    )
    op.create_index("ix_password_resets_id", "password_resets", ["id"])
    op.create_index("ix_password_resets_user_id", "password_resets", ["user_id"])

    with op.batch_alter_table("users") as b:
        b.add_column(sa.Column("google_sub", sa.String(length=255), nullable=True))
        b.add_column(sa.Column("terms_accepted_at", sa.DateTime(), nullable=True))
        b.create_unique_constraint("uq_users_google_sub", ["google_sub"])
    # Everyone who signed up through the form ticked the terms box
    op.execute("UPDATE users SET terms_accepted_at = created_at WHERE date_of_birth IS NOT NULL")

    op.create_table(
        "teams",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("code", sa.String(length=12), nullable=False),
        sa.Column("leader_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("event_id", "name", name="uq_teams_event_name"),
    )
    op.create_index("ix_teams_id", "teams", ["id"])
    op.create_index("ix_teams_event_id", "teams", ["event_id"])
    op.create_index("ix_teams_code", "teams", ["code"], unique=True)

    with op.batch_alter_table("events") as b:
        b.add_column(sa.Column("is_team_event", sa.Boolean(), nullable=False, server_default="0"))
        b.add_column(sa.Column("team_min", sa.Integer(), nullable=True))
        b.add_column(sa.Column("team_max", sa.Integer(), nullable=True))
    with op.batch_alter_table("event_registrations") as b:
        b.add_column(sa.Column("team_id", sa.Integer(), nullable=True))
        b.create_foreign_key("fk_event_registrations_team_id", "teams", ["team_id"], ["id"])
        b.create_index("ix_event_registrations_team_id", ["team_id"])

    op.create_table(
        "fest_transfers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("fest_id", sa.Integer(), sa.ForeignKey("fests.id"), nullable=False),
        sa.Column("from_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("to_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(length=12), nullable=False, server_default="pending"),
        sa.Column("keep_previous_owner", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_fest_transfers_id", "fest_transfers", ["id"])
    op.create_index("ix_fest_transfers_fest_id", "fest_transfers", ["fest_id"])
    op.create_index("ix_fest_transfers_to_user_id", "fest_transfers", ["to_user_id"])


def downgrade() -> None:
    op.drop_table("fest_transfers")
    with op.batch_alter_table("event_registrations") as b:
        b.drop_index("ix_event_registrations_team_id")
        b.drop_constraint("fk_event_registrations_team_id", type_="foreignkey")
        b.drop_column("team_id")
    with op.batch_alter_table("events") as b:
        b.drop_column("team_max")
        b.drop_column("team_min")
        b.drop_column("is_team_event")
    op.drop_table("teams")
    with op.batch_alter_table("users") as b:
        b.drop_constraint("uq_users_google_sub", type_="unique")
        b.drop_column("terms_accepted_at")
        b.drop_column("google_sub")
    op.drop_table("password_resets")
