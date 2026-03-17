"""Reusable GitHub HTTP client for OAuth and PR analysis flows."""

from __future__ import annotations

from typing import Any

import httpx

from backend.config import settings
from backend.services.github.exceptions import (
    GitHubAPIError,
    GitHubRateLimitError,
    PRNotFoundError,
    RepoNotFoundError,
)


class GitHubClient:
    """Thin async wrapper around the GitHub REST API."""

    def __init__(self, *, access_token: str | None = None, base_url: str) -> None:
        self.access_token = access_token
        self.base_url = base_url
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=20.0,
            headers=self._build_api_headers(access_token),
        )

    async def __aenter__(self) -> GitHubClient:
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def exchange_code_for_token(self, *, code: str, redirect_uri: str | None = None) -> str:
        """Exchange an OAuth code for a GitHub access token."""

        payload = {
            "client_id": settings.GITHUB_CLIENT_ID,
            "client_secret": settings.GITHUB_CLIENT_SECRET,
            "code": code,
        }
        if redirect_uri:
            payload["redirect_uri"] = redirect_uri

        async with httpx.AsyncClient(timeout=20.0) as oauth_client:
            response = await oauth_client.post(
                "https://github.com/login/oauth/access_token",
                data=payload,
                headers={
                    "Accept": "application/json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )

        self._raise_for_status(response, operation="oauth_token_exchange")
        access_token = str(response.json().get("access_token") or "").strip()
        if not access_token:
            raise GitHubAPIError(
                "GitHub no devolvio un access token valido.",
                err_code="GITHUB_ACCESS_TOKEN_MISSING",
                status_code=400,
            )
        return access_token

    async def get_current_user(self) -> dict[str, Any]:
        return await self.get("/user")

    async def get_current_user_emails(self) -> list[dict[str, Any]]:
        response = await self.get("/user/emails")
        return response if isinstance(response, list) else []

    async def get_pull_request(self, owner: str, repo: str, pr_number: int) -> dict[str, Any]:
        return await self.get(f"/repos/{owner}/{repo}/pulls/{pr_number}")

    async def list_pull_request_commits(self, owner: str, repo: str, pr_number: int) -> list[dict[str, Any]]:
        payload = await self.get(f"/repos/{owner}/{repo}/pulls/{pr_number}/commits")
        return payload if isinstance(payload, list) else []

    async def get_commit(self, owner: str, repo: str, sha: str) -> dict[str, Any]:
        return await self.get(f"/repos/{owner}/{repo}/commits/{sha}")

    async def compare_refs(self, owner: str, repo: str, base: str, head: str) -> dict[str, Any]:
        return await self.get(f"/repos/{owner}/{repo}/compare/{base}...{head}")

    async def get(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        response = await self._client.get(path, params=params)
        self._raise_for_status(response, operation=path)
        return response.json()

    def _raise_for_status(self, response: httpx.Response, *, operation: str) -> None:
        if response.status_code < 400:
            return

        message = _extract_github_message(response)
        if response.status_code == 404:
            if "/pulls/" in operation:
                raise PRNotFoundError(message, err_code="PULL_REQUEST_NOT_FOUND", status_code=404)
            raise RepoNotFoundError(message, err_code="GITHUB_REPOSITORY_NOT_FOUND", status_code=404)
        if response.status_code == 401:
            raise GitHubAPIError(
                "El token de GitHub no es valido o expiro.",
                err_code="GITHUB_TOKEN_INVALID",
                status_code=401,
            )
        if response.status_code == 403 and response.headers.get("x-ratelimit-remaining") == "0":
            raise GitHubRateLimitError(
                "GitHub rate limit exceeded.",
                err_code="GITHUB_RATE_LIMIT_EXCEEDED",
                status_code=429,
            )
        if response.status_code == 403:
            raise GitHubAPIError(
                "GitHub rechazo la solicitud por permisos insuficientes.",
                err_code="GITHUB_FORBIDDEN",
                status_code=403,
            )

        raise GitHubAPIError(
            message,
            err_code="GITHUB_API_ERROR",
            status_code=502,
        )

    @staticmethod
    def _build_api_headers(access_token: str | None) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
        return headers


def _extract_github_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return "GitHub devolvio una respuesta invalida."

    if isinstance(payload, dict):
        message = str(payload.get("message") or "").strip()
        if message:
            return message
    return "GitHub devolvio un error."
