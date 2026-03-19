"""add head_branch_missing to pr_analysis"""

revision = "a1c3e5f7b2d9"
down_revision = "9b7a6f4c2d11"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.add_column(
        "pr_analysis",
        sa.Column("head_branch_missing", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("pr_analysis", "head_branch_missing")
