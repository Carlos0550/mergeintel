"""Controllers for pull request analysis routes."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from backend.controllers.decorators import handle_controller_errors
from backend.schemas.base import ErrorResponse, SucessWithData
from backend.schemas.pr import AnalyzePRRequest
from backend.services.ai import AIProviderClient
from backend.services.github import GitHubClient
from backend.services.pr import PRService


class PRController:
    """Controller for PR analysis CRUD flows."""

    def __init__(
        self,
        *,
        db: AsyncSession,
        github_client: GitHubClient | None,
        ai_client: AIProviderClient | None,
        current_user_id: UUID,
    ) -> None:
        self.pr_service = PRService(
            session=db,
            github_client=github_client,
            ai_client=ai_client,
            current_user_id=current_user_id,
        )

    @handle_controller_errors(default_message="No se pudo analizar el PR.", default_code="PR_ANALYZE_ERROR")
    async def analyze(self, data: AnalyzePRRequest) -> SucessWithData | ErrorResponse:
        analysis = await self.pr_service.analyze_pull_request(data)
        return SucessWithData(
            success=True,
            message="PR analizado correctamente.",
            result=PRService.to_response_payload(analysis),
        )

    @handle_controller_errors(default_message="No se pudo recuperar el analisis.", default_code="PR_GET_ERROR")
    async def get_analysis(self, analysis_id: UUID) -> SucessWithData | ErrorResponse:
        analysis = await self.pr_service.get_analysis(analysis_id)
        return SucessWithData(
            success=True,
            message="Análisis de PR recuperado correctamente.",
            result=PRService.to_response_payload(analysis),
        )

    @handle_controller_errors(default_message="No se pudo recuperar el checklist.", default_code="PR_CHECKLIST_ERROR")
    async def get_checklist(self, analysis_id: UUID) -> SucessWithData | ErrorResponse:
        analysis = await self.pr_service.get_analysis(analysis_id)
        return SucessWithData(
            success=True,
            message="Checklist recuperado correctamente.",
            result=PRService.to_response_payload(analysis)["checklist"],
        )

    @handle_controller_errors(default_message="No se pudo recuperar el historial.", default_code="PR_HISTORY_ERROR")
    async def list_history(self) -> SucessWithData | ErrorResponse:
        items = await self.pr_service.list_history()
        return SucessWithData(
            success=True,
            message="Historial de PR recuperado correctamente.",
            result=[
                {
                    "id": str(item.id),
                    "repo_full_name": item.repo_full_name,
                    "pr_number": item.pr_number,
                    "pr_title": item.pr_title,
                    "status": item.status.value,
                    "risk_score": item.risk_score,
                    "created_at": item.created_at.isoformat(),
                }
                for item in items
            ],
        )

    @handle_controller_errors(default_message="No se pudo eliminar el analisis.", default_code="PR_DELETE_ERROR")
    async def delete_analysis(self, analysis_id: UUID) -> SucessWithData | ErrorResponse:
        await self.pr_service.delete_analysis(analysis_id)
        return SucessWithData(
            success=True,
            message="Análisis de PR eliminado correctamente.",
            result={"deleted": True},
        )
