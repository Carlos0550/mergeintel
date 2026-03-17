"""add oauth provider_user unique constraint"""

revision = "7f8d2a1c4b9e"
down_revision = "dbc2eba828d0"
branch_labels = None
depends_on = None

from alembic import op


def upgrade() -> None:
    """Apply the migration."""

    op.create_unique_constraint(
        "uq_oauth_provider_user",
        "OAuthAccount",
        ["provider", "provider_user_id"],
    )


def downgrade() -> None:
    """Revert the migration."""

    op.drop_constraint(
        "uq_oauth_provider_user",
        "OAuthAccount",
        type_="unique",
    )
