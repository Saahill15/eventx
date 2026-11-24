"""committee teams, titles and reporting lines for fest members

Revision ID: 0016
Revises: 0015
"""
from alembic import op
import sqlalchemy as sa

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "committee_teams",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("fest_id", sa.Integer(), sa.ForeignKey("fests.id"), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("description", sa.String(length=300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("fest_id", "name", name="uq_committee_teams_fest_name"),
    )
    op.create_index("ix_committee_teams_id", "committee_teams", ["id"])
    op.create_index("ix_committee_teams_fest_id", "committee_teams", ["fest_id"])
    with op.batch_alter_table("fest_members") as b:
        b.add_column(sa.Column("title", sa.String(length=80), nullable=True))
        b.add_column(sa.Column("committee_team_id", sa.Integer(), nullable=True))
        b.add_column(sa.Column("reports_to_id", sa.Integer(), nullable=True))
        b.create_foreign_key("fk_fest_members_team", "committee_teams", ["committee_team_id"], ["id"])
        b.create_foreign_key("fk_fest_members_reports_to", "fest_members", ["reports_to_id"], ["id"])


def downgrade() -> None:
    with op.batch_alter_table("fest_members") as b:
        b.drop_constraint("fk_fest_members_reports_to", type_="foreignkey")
        b.drop_constraint("fk_fest_members_team", type_="foreignkey")
        b.drop_column("reports_to_id")
        b.drop_column("committee_team_id")
        b.drop_column("title")
    op.drop_index("ix_committee_teams_fest_id", table_name="committee_teams")
    op.drop_index("ix_committee_teams_id", table_name="committee_teams")
    op.drop_table("committee_teams")
