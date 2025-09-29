"""add functional index for case-insensitive item lookups"""

from alembic import op
import sqlalchemy as sa


revision = "2025_05_20_120500"
down_revision = "2025_05_15_120000_add_entries_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_items_lower_name",
        "items",
        [sa.text("lower(name)")],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_items_lower_name", table_name="items")
