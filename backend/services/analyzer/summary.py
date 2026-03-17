"""LLM-backed PR summary generation."""

from __future__ import annotations

from dataclasses import dataclass

from backend.services.ai import AIProviderClient
from backend.services.analyzer.helpers import build_messages
from backend.services.analyzer.prompts import SUMMARY_SYSTEM_PROMPT, build_summary_prompt
from backend.services.analyzer.risk import RiskAnalysisResult
from backend.services.analyzer.schema import SchemaAnalysisResult
from backend.services.github.types import PRAnalysisInput


@dataclass(slots=True)
class SummaryResult:
    summary_text: str
    payload: dict


class SummaryService:
    """Generate a narrative summary from PR analysis inputs."""

    def __init__(self, ai_client: AIProviderClient) -> None:
        self.ai_client = ai_client

    async def generate_summary(
        self,
        analysis_input: PRAnalysisInput,
        schema_analysis: SchemaAnalysisResult,
        risk_analysis: RiskAnalysisResult,
        checklist: list[dict],
    ) -> SummaryResult:
        prompt = build_summary_prompt(
            analysis_input=analysis_input,
            schema_analysis=schema_analysis,
            risk_analysis=risk_analysis,
        )
        summary_text = await self.ai_client.generate_text(
            build_messages(system_prompt=SUMMARY_SYSTEM_PROMPT, user_prompt=prompt),
            temperature=0.2,
            max_tokens=1200,
        )
        payload = {
            "schema_warnings": schema_analysis.warnings,
            "risk_reasons": risk_analysis.reasons,
            "checklist": checklist,
        }
        return SummaryResult(summary_text=summary_text, payload=payload)
