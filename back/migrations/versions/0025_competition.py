"""competition between colleges: points, CL meets, name auction, results, penalties, awards

Revision ID: 0025
Revises: 0024
"""
from alembic import op
import sqlalchemy as sa

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def _id():
    return sa.Column("id", sa.Integer(), primary_key=True)


def _now(name="created_at"):
    return sa.Column(name, sa.DateTime(), nullable=False, server_default=sa.func.now())


def upgrade() -> None:
    with op.batch_alter_table("events") as b:
        b.add_column(sa.Column("points_scheme", sa.JSON(), nullable=True))

    op.create_table(
        "competition_settings",
        sa.Column("fest_id", sa.Integer(), sa.ForeignKey("fests.id"), primary_key=True),
        sa.Column("starting_points", sa.Integer(), nullable=False, server_default="500"),
        sa.Column("ranking_basis", sa.String(10), nullable=False, server_default="total"),
        sa.Column("public_leaderboard", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("default_placing_points", sa.JSON(), nullable=True),
    )
    op.create_table(
        "cl_meets", _id(),
        sa.Column("fest_id", sa.Integer(), sa.ForeignKey("fests.id"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("starts_at", sa.DateTime(), nullable=False),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", name="fk_cl_meets_creator"), nullable=True),
        _now(),
    )
    op.create_index("ix_cl_meets_fest_id", "cl_meets", ["fest_id"])
    op.create_table(
        "cl_meet_attendance",
        sa.Column("meet_id", sa.Integer(), sa.ForeignKey("cl_meets.id"), primary_key=True),
        sa.Column("contingent_id", sa.Integer(), sa.ForeignKey("contingents.id", name="fk_cl_attendance_contingent"), primary_key=True),
    )
    op.create_table(
        "cl_meet_tasks", _id(),
        sa.Column("meet_id", sa.Integer(), sa.ForeignKey("cl_meets.id"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("placing_points", sa.JSON(), nullable=True),
        _now(),
    )
    op.create_index("ix_cl_meet_tasks_meet_id", "cl_meet_tasks", ["meet_id"])
    op.create_table(
        "name_auctions", _id(),
        sa.Column("fest_id", sa.Integer(), sa.ForeignKey("fests.id"), nullable=False),
        sa.Column("meet_id", sa.Integer(), sa.ForeignKey("cl_meets.id", name="fk_name_auctions_meet"), nullable=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("status", sa.String(8), nullable=False, server_default="draft"),
        sa.Column("min_bid", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("show_highest_bid", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("opened_at", sa.DateTime(), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        _now(),
    )
    op.create_index("ix_name_auctions_fest_id", "name_auctions", ["fest_id"])
    op.create_table(
        "auction_names", _id(),
        sa.Column("auction_id", sa.Integer(), sa.ForeignKey("name_auctions.id"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("code", sa.String(30), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("winner_contingent_id", sa.Integer(), sa.ForeignKey("contingents.id", name="fk_auction_name_winner"), nullable=True),
        sa.Column("winning_bid", sa.Integer(), nullable=True),
    )
    op.create_index("ix_auction_names_auction_id", "auction_names", ["auction_id"])
    op.create_table(
        "auction_bids", _id(),
        sa.Column("auction_name_id", sa.Integer(), sa.ForeignKey("auction_names.id"), nullable=False),
        sa.Column("contingent_id", sa.Integer(), sa.ForeignKey("contingents.id", name="fk_auction_bid_contingent"), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("placed_by_id", sa.Integer(), sa.ForeignKey("users.id", name="fk_auction_bid_user"), nullable=True),
        _now(), _now("updated_at"),
        sa.UniqueConstraint("auction_name_id", "contingent_id", name="uq_auction_bid_name_contingent"),
    )
    op.create_index("ix_auction_bids_auction_name_id", "auction_bids", ["auction_name_id"])
    op.create_index("ix_auction_bids_contingent_id", "auction_bids", ["contingent_id"])
    op.create_table(
        "event_results", _id(),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("contingent_id", sa.Integer(), sa.ForeignKey("contingents.id", name="fk_event_result_contingent"), nullable=False),
        sa.Column("place", sa.Integer(), nullable=False),
        sa.Column("note", sa.String(300), nullable=True),
        _now(),
        sa.UniqueConstraint("event_id", "contingent_id", name="uq_event_result_contingent"),
    )
    op.create_index("ix_event_results_event_id", "event_results", ["event_id"])
    op.create_index("ix_event_results_contingent_id", "event_results", ["contingent_id"])
    op.create_table(
        "competition_rules", _id(),
        sa.Column("fest_id", sa.Integer(), sa.ForeignKey("fests.id"), nullable=False),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id", name="fk_competition_rule_event"), nullable=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("penalty_points", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("disqualifies", sa.Boolean(), nullable=False, server_default="0"),
        _now(),
    )
    op.create_index("ix_competition_rules_fest_id", "competition_rules", ["fest_id"])
    op.create_table(
        "contingent_penalties", _id(),
        sa.Column("fest_id", sa.Integer(), sa.ForeignKey("fests.id"), nullable=False),
        sa.Column("contingent_id", sa.Integer(), sa.ForeignKey("contingents.id", name="fk_penalty_contingent"), nullable=False),
        sa.Column("rule_id", sa.Integer(), sa.ForeignKey("competition_rules.id", name="fk_penalty_rule"), nullable=True),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id", name="fk_penalty_event"), nullable=True),
        sa.Column("points", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("disqualified", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", name="fk_penalty_creator"), nullable=True),
        _now(),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_contingent_penalties_fest_id", "contingent_penalties", ["fest_id"])
    op.create_index("ix_contingent_penalties_contingent_id", "contingent_penalties", ["contingent_id"])
    op.create_table(
        "points_entries", _id(),
        sa.Column("fest_id", sa.Integer(), sa.ForeignKey("fests.id"), nullable=False),
        sa.Column("contingent_id", sa.Integer(), sa.ForeignKey("contingents.id", name="fk_points_contingent"), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("reason", sa.String(300), nullable=False),
        sa.Column("meet_task_id", sa.Integer(), sa.ForeignKey("cl_meet_tasks.id", name="fk_points_meet_task"), nullable=True),
        sa.Column("auction_name_id", sa.Integer(), sa.ForeignKey("auction_names.id", name="fk_points_auction_name"), nullable=True),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id", name="fk_points_event"), nullable=True),
        sa.Column("penalty_id", sa.Integer(), sa.ForeignKey("contingent_penalties.id", name="fk_points_penalty"), nullable=True),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", name="fk_points_creator"), nullable=True),
        _now(),
    )
    for col in ("fest_id", "contingent_id", "meet_task_id", "auction_name_id", "event_id", "penalty_id"):
        op.create_index(f"ix_points_entries_{col}", "points_entries", [col])
    op.create_table(
        "awards", _id(),
        sa.Column("fest_id", sa.Integer(), sa.ForeignKey("fests.id"), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("basis", sa.String(12), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id", name="fk_award_event"), nullable=True),
        sa.Column("winner_contingent_id", sa.Integer(), sa.ForeignKey("contingents.id", name="fk_award_winner"), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        _now(),
    )
    op.create_index("ix_awards_fest_id", "awards", ["fest_id"])


def downgrade() -> None:
    for t in ("awards", "points_entries", "contingent_penalties", "competition_rules", "event_results", "auction_bids",
              "auction_names", "name_auctions", "cl_meet_tasks", "cl_meet_attendance", "cl_meets", "competition_settings"):
        op.drop_table(t)
    with op.batch_alter_table("events") as b:
        b.drop_column("points_scheme")
