"""Risk score heuristics for pull request analysis."""

from __future__ import annotations

from dataclasses import dataclass

from backend.services.analyzer.schema import SchemaAnalysisResult
from backend.services.github.types import PRAnalysisInput


@dataclass(slots=True)
class RiskAnalysisResult:
    score: int
    reasons: list[str]


def calculate_risk(
    analysis_input: PRAnalysisInput,
    schema_analysis: SchemaAnalysisResult,
    out_of_scope_count: int,
) -> RiskAnalysisResult:
    """Compute a bounded 1-10 risk score using static signals."""

    score = 1
    reasons: list[str] = []

    if analysis_input.divergence_days >= 14:
        score += 3
        reasons.append("La rama tiene mas de 14 dias de divergencia.")
    elif analysis_input.divergence_days >= 7:
        score += 2
        reasons.append("La rama tiene al menos una semana de divergencia.")

    if len(analysis_input.files) >= 50:
        score += 3
        reasons.append("El PR toca una cantidad muy alta de archivos.")
    elif len(analysis_input.files) >= 20:
        score += 2
        reasons.append("El PR toca varios archivos y aumenta la superficie de revision.")

    if schema_analysis.warnings:
        score += 3
        reasons.extend(schema_analysis.warnings)

    if out_of_scope_count:
        score += 2
        reasons.append("Se detectaron archivos potencialmente fuera de scope.")

    return RiskAnalysisResult(score=min(score, 10), reasons=reasons)
