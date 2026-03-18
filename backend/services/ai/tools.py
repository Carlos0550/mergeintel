"""Tool definitions and execution handlers for chat function calling."""

from __future__ import annotations

import fnmatch
import json
import logging
from dataclasses import dataclass

from backend.models.pr_analysis import PRAnalysis
from backend.services.ai.base import ToolDefinition
from backend.services.github.client import GitHubClient

logger = logging.getLogger(__name__)


@dataclass
class ToolContext:
    """Runtime context available to all tool handlers."""

    analysis: PRAnalysis  # with files, checklist_items, authors loaded
    github_client: GitHubClient | None = None


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS: list[ToolDefinition] = [
    ToolDefinition(
        name="get_file_diff",
        description=(
            "Retorna el patch/diff de un archivo específico del PR. "
            "Usa esta herramienta cuando el usuario pregunte sobre cambios concretos en un archivo."
        ),
        parameters={
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Ruta completa del archivo (tal como aparece en la lista de archivos del PR).",
                },
            },
            "required": ["file_path"],
        },
    ),
    ToolDefinition(
        name="get_checklist_item",
        description=(
            "Retorna los detalles completos de un ítem del checklist de revisión por su índice (base 0). "
            "Úsalo cuando necesites más contexto sobre un punto específico del checklist."
        ),
        parameters={
            "type": "object",
            "properties": {
                "index": {
                    "type": "integer",
                    "description": "Índice del ítem en el checklist (empezando en 0).",
                },
            },
            "required": ["index"],
        },
    ),
    ToolDefinition(
        name="get_pr_comments",
        description=(
            "Obtiene los comentarios de revisión del PR desde GitHub en tiempo real. "
            "Opcionalmente filtra por ruta de archivo."
        ),
        parameters={
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Ruta de archivo para filtrar comentarios. Si se omite, retorna todos.",
                },
            },
            "required": [],
        },
    ),
    ToolDefinition(
        name="search_files_by_pattern",
        description=(
            "Filtra los archivos cambiados en el PR por un patrón glob o substring. "
            "Útil para encontrar archivos relevantes cuando no se conoce la ruta exacta."
        ),
        parameters={
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Patrón glob (ej: '*.py', 'src/**/*.ts') o substring para buscar en las rutas.",
                },
            },
            "required": ["pattern"],
        },
    ),
    ToolDefinition(
        name="get_commits",
        description=(
            "Retorna la lista de commits del PR con su autor, mensaje, fecha y estadísticas. "
            "Usa esta herramienta cuando el usuario pregunte cuántos commits se hicieron, quién los hizo, "
            "o qué mensajes de commit contiene el PR."
        ),
        parameters={
            "type": "object",
            "properties": {
                "author": {
                    "type": "string",
                    "description": "Filtrar commits por nombre de usuario o email del autor. Si se omite, retorna todos.",
                },
            },
            "required": [],
        },
    ),
    ToolDefinition(
        name="get_risk_summary",
        description=(
            "Retorna datos estructurados de riesgo del PR: score, días de divergencia, "
            "totales de archivos/adiciones/eliminaciones y conteo de autores."
        ),
        parameters={
            "type": "object",
            "properties": {},
            "required": [],
        },
    ),
]


# ---------------------------------------------------------------------------
# Tool execution
# ---------------------------------------------------------------------------

_MAX_PATCH_LENGTH = 6000
_MAX_COMMENTS = 30


async def execute_tool(name: str, arguments: dict | None, ctx: ToolContext) -> str:
    """Execute a tool by name and return the result as a string."""
    handler = _HANDLERS.get(name)
    if handler is None:
        return json.dumps({"error": f"Herramienta desconocida: {name}"})
    try:
        return await handler(arguments or {}, ctx)
    except Exception as exc:
        logger.exception("Tool execution failed: %s", name)
        return json.dumps({"error": f"Error ejecutando {name}: {exc}"})


# --- Individual handlers ---


async def _get_file_diff(args: dict, ctx: ToolContext) -> str:
    file_path = args.get("file_path", "")
    for f in ctx.analysis.files:
        if f.path == file_path:
            patch = f.patch or ""
            if not patch:
                return json.dumps({"file": file_path, "message": "No hay patch disponible para este archivo."})
            if len(patch) > _MAX_PATCH_LENGTH:
                patch = patch[:_MAX_PATCH_LENGTH] + "\n\n... [patch truncado]"
            return json.dumps({"file": file_path, "patch": patch})
    available = [f.path for f in ctx.analysis.files[:20]]
    return json.dumps({"error": f"Archivo '{file_path}' no encontrado en el PR.", "available_files": available})


async def _get_checklist_item(args: dict, ctx: ToolContext) -> str:
    index = args.get("index", 0)
    items = ctx.analysis.checklist_items
    if not items:
        return json.dumps({"error": "No hay ítems en el checklist."})
    if index < 0 or index >= len(items):
        return json.dumps({"error": f"Índice fuera de rango. El checklist tiene {len(items)} ítems (0-{len(items) - 1})."})
    item = items[index]
    return json.dumps({
        "index": index,
        "title": item.title,
        "details": item.details or "",
        "severity": item.severity.value,
        "completed": item.completed,
    })


async def _get_pr_comments(args: dict, ctx: ToolContext) -> str:
    if ctx.github_client is None:
        return json.dumps({"error": "No hay cliente de GitHub disponible para obtener comentarios."})

    repo_full_name = ctx.analysis.repo_full_name
    parts = repo_full_name.split("/", 1)
    if len(parts) != 2:
        return json.dumps({"error": f"Nombre de repositorio inválido: {repo_full_name}"})

    owner, repo = parts
    pr_number = ctx.analysis.pr_number
    comments = await ctx.github_client.list_pr_review_comments(owner, repo, pr_number)

    file_path = args.get("file_path")
    if file_path:
        comments = [c for c in comments if c.get("path") == file_path]

    formatted: list[dict] = []
    for c in comments[:_MAX_COMMENTS]:
        formatted.append({
            "author": c.get("user", {}).get("login", "unknown"),
            "body": (c.get("body") or "")[:500],
            "path": c.get("path", ""),
            "line": c.get("line") or c.get("original_line"),
        })

    return json.dumps({"count": len(formatted), "comments": formatted})


async def _search_files_by_pattern(args: dict, ctx: ToolContext) -> str:
    pattern = args.get("pattern", "")
    if not pattern:
        return json.dumps({"error": "Se requiere un patrón de búsqueda."})

    matches: list[dict] = []
    for f in ctx.analysis.files:
        if fnmatch.fnmatch(f.path, pattern) or pattern.lower() in f.path.lower():
            matches.append({
                "path": f.path,
                "change_type": f.change_type,
                "additions": f.additions,
                "deletions": f.deletions,
            })

    if not matches:
        return json.dumps({"message": f"No se encontraron archivos con el patrón '{pattern}'.", "matches": []})
    return json.dumps({"count": len(matches), "matches": matches})


async def _get_commits(args: dict, ctx: ToolContext) -> str:
    commits = ctx.analysis.commits
    if not commits:
        return json.dumps({"message": "No hay commits registrados para este PR.", "commits": []})

    author_filter = (args.get("author") or "").lower().strip()

    # Build author lookup by id
    author_by_id = {a.id: a for a in (ctx.analysis.authors or [])}

    rows: list[dict] = []
    for c in commits:
        author = author_by_id.get(c.author_id)
        author_login = (author.github_login or author.name or author.email or "unknown") if author else "unknown"

        if author_filter and author_filter not in author_login.lower():
            continue

        rows.append({
            "sha": c.sha[:8],
            "message": (c.message or "").split("\n")[0][:120],  # first line only
            "author": author_login,
            "committed_at": c.committed_at,
            "additions": c.additions,
            "deletions": c.deletions,
        })

    # Summary by author
    by_author: dict[str, dict] = {}
    for row in rows:
        a = row["author"]
        if a not in by_author:
            by_author[a] = {"commits": 0, "additions": 0, "deletions": 0}
        by_author[a]["commits"] += 1
        by_author[a]["additions"] += row["additions"]
        by_author[a]["deletions"] += row["deletions"]

    return json.dumps({
        "total_commits": len(rows),
        "by_author": by_author,
        "commits": rows,
    })


async def _get_risk_summary(args: dict, ctx: ToolContext) -> str:
    analysis = ctx.analysis
    total_additions = sum(f.additions for f in analysis.files)
    total_deletions = sum(f.deletions for f in analysis.files)
    author_count = len(analysis.authors) if analysis.authors else 0

    result: dict = {
        "risk_score": analysis.risk_score,
        "divergence_days": analysis.divergence_days,
        "total_files": len(analysis.files),
        "total_additions": total_additions,
        "total_deletions": total_deletions,
        "author_count": author_count,
    }
    if analysis.summary_payload:
        result["summary_payload"] = analysis.summary_payload

    return json.dumps(result)


_HANDLERS: dict = {
    "get_file_diff": _get_file_diff,
    "get_checklist_item": _get_checklist_item,
    "get_pr_comments": _get_pr_comments,
    "search_files_by_pattern": _search_files_by_pattern,
    "get_commits": _get_commits,
    "get_risk_summary": _get_risk_summary,
}
