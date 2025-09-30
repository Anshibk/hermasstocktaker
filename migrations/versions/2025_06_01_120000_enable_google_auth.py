"""enable google auth and invitations"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "2025_06_01_120000_enable_google_auth"
down_revision = "2025_05_20_120500_add_items_lower_name_index"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    op.alter_column(
        "users",
        "username",
        existing_type=sa.String(length=60),
        type_=sa.String(length=120),
        existing_nullable=False,
    )
    op.alter_column(
        "users",
        "password",
        existing_type=sa.String(length=255),
        nullable=True,
    )
    op.add_column("users", sa.Column("email", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("google_sub", sa.String(length=64), nullable=True))
    op.add_column("users", sa.Column("invitation_token", sa.String(length=128), nullable=True))
    op.add_column(
        "users",
        sa.Column("invited_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("invited_by_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_users_invited_by",
        "users",
        "users",
        ["invited_by_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "uq_users_email",
        "users",
        ["email"],
        unique=True,
        postgresql_where=sa.text("email IS NOT NULL"),
    )
    op.create_index(
        "uq_users_google_sub",
        "users",
        ["google_sub"],
        unique=True,
        postgresql_where=sa.text("google_sub IS NOT NULL"),
    )
    op.create_index(
        "uq_users_invitation_token",
        "users",
        ["invitation_token"],
        unique=True,
        postgresql_where=sa.text("invitation_token IS NOT NULL"),
    )
    op.execute("UPDATE users SET email = username WHERE email IS NULL AND position('@' in username) > 0")


def downgrade() -> None:
    op.execute("UPDATE users SET email = NULL, google_sub = NULL, invitation_token = NULL, invited_at = NULL, invited_by_id = NULL")
    op.drop_index("uq_users_invitation_token", table_name="users")
    op.drop_index("uq_users_google_sub", table_name="users")
    op.drop_index("uq_users_email", table_name="users")
    op.drop_constraint("fk_users_invited_by", "users", type_="foreignkey")
    op.drop_column("users", "invited_by_id")
    op.drop_column("users", "invited_at")
    op.drop_column("users", "invitation_token")
    op.drop_column("users", "google_sub")
    op.drop_column("users", "email")
    op.alter_column(
        "users",
        "password",
        existing_type=sa.String(length=255),
        nullable=False,
    )
    op.alter_column(
        "users",
        "username",
        existing_type=sa.String(length=120),
        type_=sa.String(length=60),
        existing_nullable=False,
    )
