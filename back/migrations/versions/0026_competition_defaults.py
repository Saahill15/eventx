"""the usual points for CL meet tasks, a setting each fest can change

Revision ID: 0026
Revises: 0025
"""
from alembic import op
import sqlalchemy as sa

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("competition_settings") as b:
        b.add_column(sa.Column("default_task_points", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("competition_settings") as b:
        b.drop_column("default_task_points")
