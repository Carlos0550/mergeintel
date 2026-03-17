"""Prompt builders for PR analysis and chat."""

from __future__ import annotations

from backend.services.analyzer.helpers import truncate_text
from backend.services.analyzer.risk import RiskAnalysisResult
from backend.services.analyzer.schema import SchemaAnalysisResult
from backend.services.github.types import PRAnalysisInput


SUMMARY_SYSTEM_PROMPT = (
    "You are MergeIntel, an assistant that summarizes GitHub pull requests for engineering teams. "
    "Be concrete, technical, and action-oriented."
)

CHAT_SYSTEM_PROMPT = (
    "You are MergeIntel chat. Answer questions strictly using the persisted PR analysis context. "
    "If the answer is uncertain, say so explicitly."
)


def build_summary_prompt(
    analysis_input: PRAnalysisInput,
    schema_analysis: SchemaAnalysisResult,
    risk_analysis: RiskAnalysisResult,
) -> str:
    """Build the user prompt for the PR summary call."""

    author_lines = [
        f"- {author.github_login or author.email or key}: commits={author.commit_count}, "
        f"additions={author.additions}, deletions={author.deletions}, files={sorted(author.files)}"
        for key, author in analysis_input.authors.items()
    ]
    diff_lines = [
        f"- {item.path} ({item.change_type}, +{item.additions}/-{item.deletions})\n{truncate_text(item.patch, limit=1200)}"
        for item in analysis_input.files[:20]
    ]

    return (
        f"Repository: {analysis_input.metadata.owner}/{analysis_input.metadata.repo}\n"
        f"PR: #{analysis_input.metadata.number} - {analysis_input.metadata.title}\n"
        f"Base: {analysis_input.metadata.base_branch}\n"
        f"Head: {analysis_input.metadata.head_branch}\n"
        f"Divergence days: {analysis_input.divergence_days}\n"
        f"Risk score: {risk_analysis.score}\n"
        f"Risk reasons: {risk_analysis.reasons}\n"
        f"Schema warnings: {schema_analysis.warnings}\n"
        f"Migration files: {schema_analysis.migration_files}\n"
        "Authors:\n"
        f"{chr(10).join(author_lines)}\n\n"
        "Important file changes:\n"
        f"{chr(10).join(diff_lines)}\n\n"
        "Write a concise technical summary, key risks, and concrete next review actions."
    )


def build_chat_context(
    *,
    analysis_summary: str,
    checklist_lines: list[str],
    file_lines: list[str],
    history_lines: list[str],
    user_message: str,
) -> str:
    """Build the contextual user prompt for chat interactions."""

    return (
        f"Analysis summary:\n{truncate_text(analysis_summary, limit=3000)}\n\n"
        f"Checklist:\n{chr(10).join(checklist_lines)}\n\n"
        f"Files:\n{chr(10).join(file_lines[:40])}\n\n"
        f"Conversation history:\n{chr(10).join(history_lines[-12:])}\n\n"
        f"User question:\n{user_message}"
    )
