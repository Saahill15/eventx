"""first and last name on accounts

Revision ID: 0008
Revises: 0007
"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as b:
        b.add_column(sa.Column("first_name", sa.String(length=120), nullable=True))
        b.add_column(sa.Column("last_name", sa.String(length=120), nullable=True))
    # Existing accounts only have one name: split it at the first space
    conn = op.get_bind()
    for uid, name in conn.execute(sa.text("SELECT id, name FROM users")).fetchall():
        first, _, last = (name or "").strip().partition(" ")
        conn.execute(sa.text("UPDATE users SET first_name = :f, last_name = :l WHERE id = :i"), {"f": first or None, "l": last.strip() or None, "i": uid})


def downgrade() -> None:
    with op.batch_alter_table("users") as b:
        b.drop_column("last_name")
        b.drop_column("first_name")
