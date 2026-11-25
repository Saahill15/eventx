"""team heads and co-heads, team permissions, and the team an invitation is for

Revision ID: 0022
Revises: 0021
"""
from alembic import op
import sqlalchemy as sa

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("committee_teams") as b:
        b.add_column(sa.Column("leaders_manage_team", sa.Boolean(), nullable=False, server_default="1"))
    with op.batch_alter_table("fest_members") as b:
        b.add_column(sa.Column("team_role", sa.String(length=10), nullable=False, server_default="member"))
    with op.batch_alter_table("fest_invites") as b:
        b.add_column(sa.Column("committee_team_id", sa.Integer(), nullable=True))
        b.add_column(sa.Column("team_role", sa.String(length=10), nullable=False, server_default="member"))
        b.create_foreign_key("fk_fest_invites_team", "committee_teams", ["committee_team_id"], ["id"])


def downgrade() -> None:
    with op.batch_alter_table("fest_invites") as b:
        b.drop_constraint("fk_fest_invites_team", type_="foreignkey")
        b.drop_column("team_role")
        b.drop_column("committee_team_id")
    with op.batch_alter_table("fest_members") as b:
        b.drop_column("team_role")
    with op.batch_alter_table("committee_teams") as b:
        b.drop_column("leaders_manage_team")
