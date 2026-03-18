"""Application service for pull request analysis flows."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.exceptions import AppError
from backend.models.chat import ChatSession
from backend.models.pr_analysis import (
    AnalysisStatus,
    ChecklistSeverity,
    PRAnalysis,
    PRAnalysisAuthor,
    PRAnalysisCommit,
    PRAnalysisFile,
    PRChecklistItem,
)
from backend.schemas.pr import AnalyzePRRequest
from backend.services.ai import AIProviderClient
from backend.services.analyzer import SummaryService, analyze_schema_changes, calculate_risk, evaluate_author_scope
from backend.services.github import GitHubClient, PullRequestService, parse_pull_request_reference


class PRService:
    """Fetch, analyze, persist, and retrieve pull request analyses."""

    def __init__(
        self,
        *,
        session: AsyncSession,
        github_client: GitHubClient | None,
        ai_client: AIProviderClient | None,
        current_user_id: UUID,
    ) -> None:
        self.session = session
        self.github_client = github_client
        self.ai_client = ai_client
        self.current_user_id = current_user_id

    async def analyze_pull_request(self, data: AnalyzePRRequest) -> PRAnalysis:
        if self.github_client is None or self.ai_client is None:
            raise AppError(
                "El cliente de GitHub y el proveedor de IA son obligatorios para analizar un PR.",
                err_code="PR_ANALYSIS_DEPENDENCY_ERROR",
                status_code=500,
            )

        owner, repo, pr_number = parse_pull_request_reference(
            pr_url=data.pr_url,
            owner=data.owner,
            repo=data.repo,
            pr_number=data.pr_number,
        )

        pull_request_service = PullRequestService(self.github_client)
        analysis_input = await pull_request_service.build_analysis_input(owner, repo, pr_number)
        schema_analysis = analyze_schema_changes(analysis_input.files)

        out_of_scope_count = 0
        for author in analysis_input.authors.values():
            scope_evaluation = evaluate_author_scope(author, analysis_input.files, data.author_scopes)
            author_key = author.key
            author_scope_files: dict[str, str] = {}
            for file_item in analysis_input.files:
                if file_item.author_key != author_key:
                    continue
                reason = scope_evaluation.out_of_scope_paths.get(file_item.path)
                if reason:
                    author_scope_files[file_item.path] = reason
                    out_of_scope_count += 1
            author.inferred_scope = scope_evaluation.inferred_scope
            author.scope_confidence = scope_evaluation.confidence
            author.out_of_scope_paths = author_scope_files

        risk_analysis = calculate_risk(analysis_input, schema_analysis, out_of_scope_count)
        checklist = self._build_checklist(schema_analysis, risk_analysis)
        if analysis_input.head_branch_missing:
            checklist.insert(
                0,
                {
                    "title": "La rama head ya no existe en el repositorio",
                    "details": f"La rama '{analysis_input.metadata.head_branch}' fue eliminada. El PR no puede mergearse hasta que se restaure o se cambie la rama base.",
                    "severity": ChecklistSeverity.CRITICAL.value,
                },
            )
        summary_service = SummaryService(self.ai_client)
        summary_result = await summary_service.generate_summary(
            analysis_input=analysis_input,
            schema_analysis=schema_analysis,
            risk_analysis=risk_analysis,
            checklist=checklist,
        )

        analysis = await self._get_existing_analysis(owner=owner, repo=repo, pr_number=pr_number)
        if analysis is None:
            analysis = PRAnalysis(
                user_id=self.current_user_id,
                repo_full_name=f"{owner}/{repo}",
                pr_number=analysis_input.metadata.number,
                pr_title=analysis_input.metadata.title,
                pr_url=analysis_input.metadata.url,
                base_branch=analysis_input.metadata.base_branch,
                head_branch=analysis_input.metadata.head_branch,
                status=AnalysisStatus.PROCESSING,
            )
            self.session.add(analysis)
            await self.session.flush()
        else:
            await self._clear_analysis_children(analysis.id)
            analysis.pr_title = analysis_input.metadata.title
            analysis.pr_url = analysis_input.metadata.url
            analysis.base_branch = analysis_input.metadata.base_branch
            analysis.head_branch = analysis_input.metadata.head_branch
            analysis.status = AnalysisStatus.PROCESSING
            analysis.error_message = None

        author_records: dict[str, PRAnalysisAuthor] = {}
        for author in analysis_input.authors.values():
            record = PRAnalysisAuthor(
                analysis_id=analysis.id,
                github_login=author.github_login,
                name=author.name,
                email=author.email,
                commit_count=author.commit_count,
                additions=author.additions,
                deletions=author.deletions,
                inferred_scope=getattr(author, "inferred_scope", None),
                scope_confidence=getattr(author, "scope_confidence", None),
            )
            self.session.add(record)
            await self.session.flush()
            author_records[author.key] = record

        commit_records: dict[str, PRAnalysisCommit] = {}
        for commit in analysis_input.commits:
            record = PRAnalysisCommit(
                analysis_id=analysis.id,
                author_id=author_records.get(commit.author_key).id if commit.author_key in author_records else None,
                sha=commit.sha,
                message=commit.message,
                committed_at=commit.committed_at,
                additions=commit.additions,
                deletions=commit.deletions,
            )
            self.session.add(record)
            await self.session.flush()
            commit_records[commit.sha] = record

        for file_item in analysis_input.files:
            out_of_scope_paths = getattr(analysis_input.authors.get(file_item.author_key or ""), "out_of_scope_paths", {})
            reason = out_of_scope_paths.get(file_item.path) if out_of_scope_paths else None
            self.session.add(
                PRAnalysisFile(
                    analysis_id=analysis.id,
                    author_id=author_records.get(file_item.author_key).id if file_item.author_key in author_records else None,
                    commit_id=commit_records.get(file_item.commit_sha).id if file_item.commit_sha in commit_records else None,
                    path=file_item.path,
                    change_type=file_item.change_type,
                    additions=file_item.additions,
                    deletions=file_item.deletions,
                    patch=file_item.patch,
                    patch_truncated=file_item.patch_truncated,
                    is_schema_change=file_item.path in schema_analysis.migration_files
                    or file_item.path in schema_analysis.orm_model_files
                    or file_item.path in schema_analysis.sql_files,
                    out_of_scope=reason is not None,
                    scope_reason=reason,
                )
            )

        for item in checklist:
            self.session.add(
                PRChecklistItem(
                    analysis_id=analysis.id,
                    title=item["title"],
                    details=item["details"],
                    severity=ChecklistSeverity(item["severity"]),
                    completed=False,
                )
            )

        analysis.summary_text = summary_result.summary_text
        analysis.summary_payload = summary_result.payload
        analysis.risk_score = risk_analysis.score
        analysis.divergence_days = analysis_input.divergence_days
        analysis.head_branch_missing = analysis_input.head_branch_missing
        analysis.status = AnalysisStatus.DONE
        await self.session.commit()

        return await self.get_analysis(analysis.id)

    async def mark_analysis_error(
        self,
        *,
        owner: str,
        repo: str,
        pr_number: int,
        error_message: str,
    ) -> PRAnalysis:
        analysis = await self._get_existing_analysis(owner=owner, repo=repo, pr_number=pr_number)
        if analysis is None:
            analysis = PRAnalysis(
                user_id=self.current_user_id,
                repo_full_name=f"{owner}/{repo}",
                pr_number=pr_number,
                pr_title=f"PR #{pr_number}",
                pr_url=f"https://github.com/{owner}/{repo}/pull/{pr_number}",
                base_branch="main",
                head_branch="",
                status=AnalysisStatus.ERROR,
                error_message=error_message,
            )
            self.session.add(analysis)
        else:
            analysis.status = AnalysisStatus.ERROR
            analysis.error_message = error_message
        await self.session.commit()
        return analysis

    async def get_analysis(self, analysis_id: UUID) -> PRAnalysis:
        result = await self.session.execute(
            select(PRAnalysis)
            .where(PRAnalysis.id == analysis_id, PRAnalysis.user_id == self.current_user_id)
            .options(
                selectinload(PRAnalysis.authors),
                selectinload(PRAnalysis.commits),
                selectinload(PRAnalysis.files),
                selectinload(PRAnalysis.checklist_items),
                selectinload(PRAnalysis.chat_sessions),
            )
        )
        analysis = result.scalar_one_or_none()
        if analysis is None:
            raise AppError(
                "El analisis solicitado no existe.",
                err_code="PR_ANALYSIS_NOT_FOUND",
                status_code=404,
            )
        return analysis

    async def list_history(self) -> list[PRAnalysis]:
        result = await self.session.execute(
            select(PRAnalysis)
            .where(PRAnalysis.user_id == self.current_user_id)
            .order_by(PRAnalysis.created_at.desc())
        )
        return list(result.scalars().all())

    async def delete_analysis(self, analysis_id: UUID) -> None:
        analysis = await self.get_analysis(analysis_id)
        await self.session.delete(analysis)
        await self.session.commit()

    async def _get_existing_analysis(self, *, owner: str, repo: str, pr_number: int) -> PRAnalysis | None:
        result = await self.session.execute(
            select(PRAnalysis).where(
                PRAnalysis.user_id == self.current_user_id,
                PRAnalysis.repo_full_name == f"{owner}/{repo}",
                PRAnalysis.pr_number == pr_number,
            )
        )
        return result.scalar_one_or_none()

    async def _clear_analysis_children(self, analysis_id: UUID) -> None:
        await self.session.execute(delete(PRChecklistItem).where(PRChecklistItem.analysis_id == analysis_id))
        await self.session.execute(delete(ChatSession).where(ChatSession.analysis_id == analysis_id))
        await self.session.execute(delete(PRAnalysisFile).where(PRAnalysisFile.analysis_id == analysis_id))
        await self.session.execute(delete(PRAnalysisCommit).where(PRAnalysisCommit.analysis_id == analysis_id))
        await self.session.execute(delete(PRAnalysisAuthor).where(PRAnalysisAuthor.analysis_id == analysis_id))

    @staticmethod
    def _build_checklist(schema_analysis, risk_analysis) -> list[dict[str, str]]:
        checklist: list[dict[str, str]] = []
        if schema_analysis.migration_files or schema_analysis.orm_model_files or schema_analysis.sql_files:
            schema_details: list[str] = []
            if schema_analysis.migration_files:
                schema_details.append(
                    f"Migraciones detectadas: {', '.join(schema_analysis.migration_files[:5])}"
                )
            if schema_analysis.orm_model_files:
                schema_details.append(
                    f"Modelos ORM tocados: {', '.join(schema_analysis.orm_model_files[:5])}"
                )
            if schema_analysis.sql_files:
                schema_details.append(
                    f"Archivos SQL tocados: {', '.join(schema_analysis.sql_files[:5])}"
                )
            checklist.append(
                {
                    "title": "Validar cambios de schema antes del merge",
                    "details": " | ".join(schema_details),
                    "severity": ChecklistSeverity.HIGH.value,
                }
            )
        for warning in schema_analysis.warnings:
            checklist.append(
                {
                    "title": "Revisar migraciones y schema",
                    "details": warning,
                    "severity": ChecklistSeverity.CRITICAL.value,
                }
            )
        for reason in risk_analysis.reasons:
            checklist.append(
                {
                    "title": "Revisar riesgo del PR",
                    "details": reason,
                    "severity": ChecklistSeverity.MEDIUM.value,
                }
            )
        if not checklist:
            checklist.append(
                {
                    "title": "Validación general",
                    "details": "No se detectaron alertas estaticas fuertes, revisar cobertura y comportamiento funcional.",
                    "severity": ChecklistSeverity.LOW.value,
                }
            )
        return checklist

    @staticmethod
    def to_response_payload(analysis: PRAnalysis) -> dict:
        return {
            "id": str(analysis.id),
            "repo_full_name": analysis.repo_full_name,
            "pr_number": analysis.pr_number,
            "pr_title": analysis.pr_title,
            "pr_url": analysis.pr_url,
            "base_branch": analysis.base_branch,
            "head_branch": analysis.head_branch,
            "status": analysis.status.value,
            "summary_text": analysis.summary_text,
            "summary_payload": analysis.summary_payload,
            "risk_score": analysis.risk_score,
            "divergence_days": analysis.divergence_days,
            "head_branch_missing": analysis.head_branch_missing,
            "error_message": analysis.error_message,
            "authors": [
                {
                    "id": str(item.id),
                    "github_login": item.github_login,
                    "name": item.name,
                    "email": item.email,
                    "commit_count": item.commit_count,
                    "additions": item.additions,
                    "deletions": item.deletions,
                    "inferred_scope": item.inferred_scope,
                    "scope_confidence": item.scope_confidence,
                }
                for item in analysis.authors
            ],
            "commits": [
                {
                    "id": str(item.id),
                    "author_id": str(item.author_id) if item.author_id else None,
                    "sha": item.sha,
                    "message": item.message,
                    "committed_at": item.committed_at,
                    "additions": item.additions,
                    "deletions": item.deletions,
                }
                for item in analysis.commits
            ],
            "files": [
                {
                    "id": str(item.id),
                    "author_id": str(item.author_id) if item.author_id else None,
                    "commit_id": str(item.commit_id) if item.commit_id else None,
                    "path": item.path,
                    "change_type": item.change_type,
                    "additions": item.additions,
                    "deletions": item.deletions,
                    "patch_truncated": item.patch_truncated,
                    "is_schema_change": item.is_schema_change,
                    "out_of_scope": item.out_of_scope,
                    "scope_reason": item.scope_reason,
                }
                for item in analysis.files
            ],
            "checklist": [
                {
                    "id": str(item.id),
                    "title": item.title,
                    "details": item.details,
                    "severity": item.severity.value,
                    "completed": item.completed,
                }
                for item in analysis.checklist_items
            ],
        }
