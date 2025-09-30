"""Enable Google-based sign in"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "2025_06_05_120000_enable_google_signin"
down_revision = "2025_05_20_120500_add_items_lower_name_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("google_sub", sa.String(length=255), nullable=True))
    op.create_unique_constraint("uq_users_google_sub", "users", ["google_sub"])

    connection = op.get_bind()
    connection.execute(sa.text("UPDATE users SET username = lower(username)"))
    connection.execute(sa.text("UPDATE users SET google_sub = NULL WHERE google_sub = ''"))


def downgrade() -> None:
    op.drop_constraint("uq_users_google_sub", "users", type_="unique")
    op.drop_column("users", "google_sub")
