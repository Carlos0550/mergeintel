"""Static schema and migration analysis."""

from __future__ import annotations

from dataclasses import dataclass

from backend.services.github.types import PRFileChange


@dataclass(slots=True)
class SchemaAnalysisResult:
    migration_files: list[str]
    orm_model_files: list[str]
    sql_files: list[str]
    warnings: list[str]


def analyze_schema_changes(files: list[PRFileChange]) -> SchemaAnalysisResult:
    """Detect schema-related changes and common migration gaps."""

    migration_files = [
        item.path for item in files if item.path.startswith("alembic/versions/") or "/migrations/" in item.path
    ]
    orm_model_files = [item.path for item in files if "/models/" in item.path or item.path.endswith("models.py")]
    sql_files = [item.path for item in files if item.path.endswith(".sql")]

    warnings: list[str] = []
    if orm_model_files and not migration_files:
        warnings.append("Se detectaron cambios en modelos ORM sin una migracion asociada.")
    if sql_files and not migration_files:
        warnings.append("Hay cambios SQL sin una migracion versionada visible en el PR.")

    return SchemaAnalysisResult(
        migration_files=migration_files,
        orm_model_files=orm_model_files,
        sql_files=sql_files,
        warnings=warnings,
    )
