"""add sessions pr analysis and chat tables"""

revision = "9b7a6f4c2d11"
down_revision = "7f8d2a1c4b9e"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


analysis_status = postgresql.ENUM(
    "pending",
    "processing",
    "done",
    "error",
    name="analysis_status",
    create_type=False,
)
checklist_severity = postgresql.ENUM(
    "low",
    "medium",
    "high",
    "critical",
    name="checklist_severity",
    create_type=False,
)
chat_role = postgresql.ENUM(
    "user",
    "assistant",
    "system",
    name="chat_role",
    create_type=False,
)


def upgrade() -> None:
    """Apply the migration."""

    analysis_status.create(op.get_bind(), checkfirst=True)
    checklist_severity.create(op.get_bind(), checkfirst=True)
    chat_role.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "user_session",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(op.f("ix_user_session_user_id"), "user_session", ["user_id"], unique=False)
    op.create_index(op.f("ix_user_session_token_hash"), "user_session", ["token_hash"], unique=False)
    op.create_index(op.f("ix_user_session_expires_at"), "user_session", ["expires_at"], unique=False)

    op.create_table(
        "pr_analysis",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("repo_full_name", sa.String(length=255), nullable=False),
        sa.Column("pr_number", sa.Integer(), nullable=False),
        sa.Column("pr_title", sa.String(length=500), nullable=False),
        sa.Column("pr_url", sa.Text(), nullable=False),
        sa.Column("base_branch", sa.String(length=255), nullable=False),
        sa.Column("head_branch", sa.String(length=255), nullable=False),
        sa.Column("status", analysis_status, server_default="pending", nullable=False),
        sa.Column("summary_text", sa.Text(), nullable=True),
        sa.Column("summary_payload", sa.JSON(), nullable=True),
        sa.Column("risk_score", sa.Integer(), server_default="1", nullable=False),
        sa.Column("divergence_days", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_pr_analysis_user_id"), "pr_analysis", ["user_id"], unique=False)
    op.create_index(op.f("ix_pr_analysis_repo_full_name"), "pr_analysis", ["repo_full_name"], unique=False)
    op.create_index(op.f("ix_pr_analysis_pr_number"), "pr_analysis", ["pr_number"], unique=False)

    op.create_table(
        "pr_analysis_author",
        sa.Column("analysis_id", sa.Uuid(), nullable=False),
        sa.Column("github_login", sa.String(length=255), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("commit_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("additions", sa.Integer(), server_default="0", nullable=False),
        sa.Column("deletions", sa.Integer(), server_default="0", nullable=False),
        sa.Column("inferred_scope", sa.Text(), nullable=True),
        sa.Column("scope_confidence", sa.Integer(), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["analysis_id"], ["pr_analysis.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_pr_analysis_author_analysis_id"), "pr_analysis_author", ["analysis_id"], unique=False)
    op.create_index(op.f("ix_pr_analysis_author_github_login"), "pr_analysis_author", ["github_login"], unique=False)

    op.create_table(
        "pr_analysis_commit",
        sa.Column("analysis_id", sa.Uuid(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=True),
        sa.Column("sha", sa.String(length=64), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("committed_at", sa.String(length=64), nullable=False),
        sa.Column("additions", sa.Integer(), server_default="0", nullable=False),
        sa.Column("deletions", sa.Integer(), server_default="0", nullable=False),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["analysis_id"], ["pr_analysis.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_id"], ["pr_analysis_author.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_pr_analysis_commit_analysis_id"), "pr_analysis_commit", ["analysis_id"], unique=False)
    op.create_index(op.f("ix_pr_analysis_commit_author_id"), "pr_analysis_commit", ["author_id"], unique=False)
    op.create_index(op.f("ix_pr_analysis_commit_sha"), "pr_analysis_commit", ["sha"], unique=False)

    op.create_table(
        "pr_analysis_file",
        sa.Column("analysis_id", sa.Uuid(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=True),
        sa.Column("commit_id", sa.Uuid(), nullable=True),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("change_type", sa.String(length=32), nullable=False),
        sa.Column("additions", sa.Integer(), server_default="0", nullable=False),
        sa.Column("deletions", sa.Integer(), server_default="0", nullable=False),
        sa.Column("patch", sa.Text(), nullable=True),
        sa.Column("patch_truncated", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_schema_change", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("out_of_scope", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("scope_reason", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["analysis_id"], ["pr_analysis.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_id"], ["pr_analysis_author.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["commit_id"], ["pr_analysis_commit.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_pr_analysis_file_analysis_id"), "pr_analysis_file", ["analysis_id"], unique=False)
    op.create_index(op.f("ix_pr_analysis_file_author_id"), "pr_analysis_file", ["author_id"], unique=False)
    op.create_index(op.f("ix_pr_analysis_file_commit_id"), "pr_analysis_file", ["commit_id"], unique=False)

    op.create_table(
        "pr_checklist_item",
        sa.Column("analysis_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("severity", checklist_severity, server_default="medium", nullable=False),
        sa.Column("completed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["analysis_id"], ["pr_analysis.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_pr_checklist_item_analysis_id"), "pr_checklist_item", ["analysis_id"], unique=False)

    op.create_table(
        "chat_session",
        sa.Column("analysis_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["analysis_id"], ["pr_analysis.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_chat_session_analysis_id"), "chat_session", ["analysis_id"], unique=False)
    op.create_index(op.f("ix_chat_session_user_id"), "chat_session", ["user_id"], unique=False)

    op.create_table(
        "chat_message",
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("role", chat_role, nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["chat_session.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_chat_message_session_id"), "chat_message", ["session_id"], unique=False)


def downgrade() -> None:
    """Revert the migration."""

    op.drop_index(op.f("ix_chat_message_session_id"), table_name="chat_message")
    op.drop_table("chat_message")
    op.drop_index(op.f("ix_chat_session_user_id"), table_name="chat_session")
    op.drop_index(op.f("ix_chat_session_analysis_id"), table_name="chat_session")
    op.drop_table("chat_session")
    op.drop_index(op.f("ix_pr_checklist_item_analysis_id"), table_name="pr_checklist_item")
    op.drop_table("pr_checklist_item")
    op.drop_index(op.f("ix_pr_analysis_file_commit_id"), table_name="pr_analysis_file")
    op.drop_index(op.f("ix_pr_analysis_file_author_id"), table_name="pr_analysis_file")
    op.drop_index(op.f("ix_pr_analysis_file_analysis_id"), table_name="pr_analysis_file")
    op.drop_table("pr_analysis_file")
    op.drop_index(op.f("ix_pr_analysis_commit_sha"), table_name="pr_analysis_commit")
    op.drop_index(op.f("ix_pr_analysis_commit_author_id"), table_name="pr_analysis_commit")
    op.drop_index(op.f("ix_pr_analysis_commit_analysis_id"), table_name="pr_analysis_commit")
    op.drop_table("pr_analysis_commit")
    op.drop_index(op.f("ix_pr_analysis_author_github_login"), table_name="pr_analysis_author")
    op.drop_index(op.f("ix_pr_analysis_author_analysis_id"), table_name="pr_analysis_author")
    op.drop_table("pr_analysis_author")
    op.drop_index(op.f("ix_pr_analysis_pr_number"), table_name="pr_analysis")
    op.drop_index(op.f("ix_pr_analysis_repo_full_name"), table_name="pr_analysis")
    op.drop_index(op.f("ix_pr_analysis_user_id"), table_name="pr_analysis")
    op.drop_table("pr_analysis")
    op.drop_index(op.f("ix_user_session_expires_at"), table_name="user_session")
    op.drop_index(op.f("ix_user_session_token_hash"), table_name="user_session")
    op.drop_index(op.f("ix_user_session_user_id"), table_name="user_session")
    op.drop_table("user_session")

    chat_role.drop(op.get_bind(), checkfirst=True)
    checklist_severity.drop(op.get_bind(), checkfirst=True)
    analysis_status.drop(op.get_bind(), checkfirst=True)
