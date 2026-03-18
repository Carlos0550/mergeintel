"""Prompt builders for PR analysis and chat."""

from __future__ import annotations

from backend.services.analyzer.helpers import truncate_text
from backend.services.analyzer.risk import RiskAnalysisResult
from backend.services.analyzer.schema import SchemaAnalysisResult
from backend.services.github.types import PRAnalysisInput


SUMMARY_SYSTEM_PROMPT = (
    "Eres MergeIntel, un asistente técnico que resume pull requests para equipos de ingeniería. "
    "Responde siempre en español. Sé concreto, técnico y orientado a acciones. "
    "No mezcles idiomas salvo nombres propios, rutas, identificadores o texto original del código."
)

CHAT_SYSTEM_PROMPT_WITH_TOOLS = (
    "Eres el chat técnico de MergeIntel. Responde siempre en español.\n\n"
    "Tienes acceso a las siguientes herramientas para obtener datos detallados del PR bajo demanda:\n"
    "- get_file_diff(file_path): Obtiene el patch/diff de un archivo específico.\n"
    "- get_checklist_item(index): Obtiene detalles completos de un ítem del checklist.\n"
    "- get_pr_comments(file_path?): Obtiene comentarios de revisión del PR desde GitHub.\n"
    "- search_files_by_pattern(pattern): Busca archivos cambiados por patrón glob o substring.\n"
    "- get_commits(author?): Lista los commits del PR con autor, mensaje y estadísticas. Filtra por autor si se especifica.\n"
    "- get_risk_summary(): Obtiene datos estructurados de riesgo del PR.\n\n"
    "Cuándo usar herramientas:\n"
    "- Usa get_file_diff cuando el usuario pregunte sobre cambios específicos en un archivo.\n"
    "- Usa search_files_by_pattern cuando necesites encontrar archivos relevantes.\n"
    "- Usa get_pr_comments para ver lo que otros revisores han comentado.\n"
    "- Usa get_commits cuando pregunten cuántos commits hay, quién los hizo o los mensajes de commit.\n"
    "- Usa get_risk_summary para dar datos cuantitativos de riesgo.\n\n"
    "Cuándo NO usar herramientas:\n"
    "- Si la información ya está en el contexto del resumen o la lista de archivos, úsala directamente.\n"
    "- No llames herramientas de forma especulativa; solo cuando la información sea necesaria para responder.\n\n"
    "Formato de respuesta:\n"
    "- Cuando muestres un diff o patch, SIEMPRE envuélvelo en un bloque de código markdown con lenguaje 'diff':\n"
    "  ```diff\n"
    "  @@ -1,3 +1,3 @@\n"
    "  -linea eliminada\n"
    "  +linea agregada\n"
    "  ```\n"
    "- No insertes el patch como texto plano; usa siempre el bloque ```diff.\n"
    "- Para rutas de archivo, usa backticks inline: `src/archivo.ts`.\n\n"
    "Si algo no es seguro, dilo explícitamente."
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
        f"Repositorio: {analysis_input.metadata.owner}/{analysis_input.metadata.repo}\n"
        f"PR: #{analysis_input.metadata.number} - {analysis_input.metadata.title}\n"
        f"Rama base: {analysis_input.metadata.base_branch}\n"
        f"Rama head: {analysis_input.metadata.head_branch}\n"
        f"Días de divergencia: {analysis_input.divergence_days}\n"
        f"Puntaje de riesgo: {risk_analysis.score}\n"
        f"Motivos de riesgo: {risk_analysis.reasons}\n"
        f"Advertencias de schema: {schema_analysis.warnings}\n"
        f"Archivos de migración: {schema_analysis.migration_files}\n"
        "Autores:\n"
        f"{chr(10).join(author_lines)}\n\n"
        "Cambios importantes en archivos:\n"
        f"{chr(10).join(diff_lines)}\n\n"
        "Escribe un resumen técnico conciso, los riesgos principales y las próximas acciones concretas de revisión. "
        "Todo el texto de salida debe estar en español."
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
        f"Resumen del análisis:\n{truncate_text(analysis_summary, limit=3000)}\n\n"
        f"Checklist:\n{chr(10).join(checklist_lines)}\n\n"
        f"Archivos:\n{chr(10).join(file_lines[:40])}\n\n"
        f"Historial de conversación:\n{chr(10).join(history_lines[-12:])}\n\n"
        f"Pregunta del usuario:\n{user_message}"
    )
