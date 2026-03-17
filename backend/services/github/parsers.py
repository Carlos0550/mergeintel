"""Helpers for parsing GitHub pull request references and payloads."""

from __future__ import annotations

from urllib.parse import urlparse

from backend.exceptions import AppError


def parse_pull_request_reference(
    *,
    pr_url: str | None = None,
    owner: str | None = None,
    repo: str | None = None,
    pr_number: int | None = None,
) -> tuple[str, str, int]:
    """Normalize a PR reference coming from URL or explicit coordinates."""

    if pr_url:
        return _parse_pull_request_url(pr_url)

    if owner and repo and pr_number is not None:
        return owner.strip(), repo.strip(), pr_number

    raise AppError(
        "Debes proporcionar una URL de PR o owner/repo/pr_number.",
        err_code="INVALID_PR_REFERENCE",
        status_code=400,
    )


def build_repo_full_name(owner: str, repo: str) -> str:
    """Return the canonical owner/repo representation."""

    return f"{owner.strip()}/{repo.strip()}"


def truncate_patch(patch: str | None, *, limit: int = 4000) -> tuple[str | None, bool]:
    """Truncate large patches to keep prompts and persistence bounded."""

    if not patch:
        return None, False
    if len(patch) <= limit:
        return patch, False
    return f"{patch[:limit].rstrip()}\n\n... [truncated]", True


def _parse_pull_request_url(pr_url: str) -> tuple[str, str, int]:
    parsed = urlparse(pr_url.strip())
    parts = [part for part in parsed.path.split("/") if part]
    if parsed.netloc not in {"github.com", "www.github.com"} or len(parts) < 4 or parts[2] != "pull":
        raise AppError(
            "La URL del pull request no es valida.",
            err_code="INVALID_PR_URL",
            status_code=400,
        )

    owner, repo, _, raw_number = parts[:4]
    try:
        number = int(raw_number)
    except ValueError as exc:
        raise AppError(
            "El numero de PR de la URL no es valido.",
            err_code="INVALID_PR_URL",
            status_code=400,
        ) from exc
    return owner, repo, number
