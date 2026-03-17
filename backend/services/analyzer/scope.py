"""Author scope analysis helpers."""

from __future__ import annotations

from dataclasses import dataclass

from backend.services.github.types import PRAuthor, PRFileChange


@dataclass(slots=True)
class ScopeEvaluation:
    inferred_scope: str | None
    confidence: int | None
    out_of_scope_paths: dict[str, str]


def evaluate_author_scope(
    author: PRAuthor,
    files: list[PRFileChange],
    author_scopes: dict[str, list[str]],
) -> ScopeEvaluation:
    """Evaluate touched files against explicit scopes or infer a lightweight scope summary."""

    scope_keys = [author.github_login, author.email, author.key]
    expected_prefixes: list[str] = []
    for scope_key in scope_keys:
        if scope_key and scope_key in author_scopes:
            expected_prefixes = [prefix.strip("/") for prefix in author_scopes[scope_key] if prefix.strip()]
            break

    author_files = [item for item in files if item.author_key == author.key]
    if expected_prefixes:
        out_of_scope: dict[str, str] = {}
        for item in author_files:
            normalized_path = item.path.strip("/")
            if not any(
                normalized_path == prefix or normalized_path.startswith(f"{prefix}/")
                for prefix in expected_prefixes
            ):
                out_of_scope[item.path] = "El archivo no coincide con los prefijos declarados para el autor."
        return ScopeEvaluation(
            inferred_scope=", ".join(expected_prefixes),
            confidence=100,
            out_of_scope_paths=out_of_scope,
        )

    inferred_roots = sorted({item.path.split("/", maxsplit=1)[0] for item in author_files if item.path})
    inferred_scope = ", ".join(inferred_roots[:5]) if inferred_roots else None
    return ScopeEvaluation(
        inferred_scope=inferred_scope,
        confidence=40 if inferred_scope else None,
        out_of_scope_paths={},
    )
