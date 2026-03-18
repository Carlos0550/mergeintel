"""Pull request fetching and mapping services."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from backend.services.github.client import GitHubClient
from backend.services.github.exceptions import BranchNotFoundError
from backend.services.github.parsers import build_repo_full_name, truncate_patch
from backend.services.github.types import PRAnalysisInput, PRAuthor, PRCommit, PRFileChange, PRMetadata


class PullRequestService:
    """Fetch and normalize a pull request into a reusable internal representation."""

    def __init__(self, github_client: GitHubClient) -> None:
        self.github_client = github_client

    async def build_analysis_input(self, owner: str, repo: str, pr_number: int) -> PRAnalysisInput:
        pr_payload = await self.github_client.get_pull_request(owner, repo, pr_number)
        metadata = PRMetadata(
            owner=owner,
            repo=repo,
            number=pr_number,
            title=str(pr_payload.get("title") or ""),
            body=str(pr_payload.get("body") or ""),
            author_login=_nested_value(pr_payload, "user", "login"),
            base_branch=_nested_value(pr_payload, "base", "ref") or "main",
            head_branch=_nested_value(pr_payload, "head", "ref") or "",
            url=str(pr_payload.get("html_url") or f"https://github.com/{build_repo_full_name(owner, repo)}/pull/{pr_number}"),
            state=str(pr_payload.get("state") or "open"),
        )

        commit_payloads = await self.github_client.list_pull_request_commits(owner, repo, pr_number)
        authors: dict[str, PRAuthor] = {}
        commits: list[PRCommit] = []
        files: list[PRFileChange] = []

        for commit_payload in commit_payloads:
            commit = await self._build_commit(owner, repo, commit_payload)
            commits.append(commit)
            author = authors.setdefault(
                commit.author_key,
                PRAuthor(
                    key=commit.author_key,
                    github_login=commit.github_login,
                    name=commit.author_name,
                    email=commit.author_email,
                ),
            )
            author.commit_count += 1
            author.additions += commit.additions
            author.deletions += commit.deletions

        files_by_path: dict[str, PRFileChange] = {}
        author_by_path: dict[str, list[str]] = defaultdict(list)
        for commit in commits:
            commit_details = await self.github_client.get_commit(owner, repo, commit.sha)
            for item in commit_details.get("files", []):
                patch, truncated = truncate_patch(item.get("patch"))
                path = str(item.get("filename") or "")
                if not path:
                    continue
                file_change = files_by_path.get(path)
                if file_change is None:
                    file_change = PRFileChange(
                        path=path,
                        change_type=str(item.get("status") or "modified"),
                        additions=int(item.get("additions") or 0),
                        deletions=int(item.get("deletions") or 0),
                        patch=patch,
                        patch_truncated=truncated,
                        author_key=commit.author_key,
                        commit_sha=commit.sha,
                    )
                    files_by_path[path] = file_change
                else:
                    file_change.additions += int(item.get("additions") or 0)
                    file_change.deletions += int(item.get("deletions") or 0)
                    if not file_change.patch and patch:
                        file_change.patch = patch
                        file_change.patch_truncated = truncated
                author_by_path[path].append(commit.author_key)

        for path, file_change in files_by_path.items():
            owners = author_by_path.get(path, [])
            if owners:
                file_change.author_key = owners[-1]
            files.append(file_change)
            if file_change.author_key and file_change.author_key in authors:
                authors[file_change.author_key].files.add(path)

        head_branch_missing = False
        try:
            divergence_days = await self._compute_divergence_days(owner, repo, metadata.base_branch, metadata.head_branch)
        except BranchNotFoundError:
            divergence_days = 0
            head_branch_missing = True

        return PRAnalysisInput(
            metadata=metadata,
            authors=authors,
            commits=commits,
            files=files,
            divergence_days=divergence_days,
            head_branch_missing=head_branch_missing,
        )

    async def _build_commit(self, owner: str, repo: str, payload: dict) -> PRCommit:
        sha = str(payload.get("sha") or "")
        commit_details = payload.get("commit") or {}
        author_payload = payload.get("author") or {}
        commit_author_payload = commit_details.get("author") or {}
        author_login = str(author_payload.get("login") or "").strip() or None
        author_email = str(commit_author_payload.get("email") or "").strip() or None
        author_name = str(commit_author_payload.get("name") or "").strip() or author_login
        author_key = author_login or author_email or sha

        detailed_payload = await self.github_client.get_commit(owner, repo, sha)
        stats = detailed_payload.get("stats") or {}

        return PRCommit(
            sha=sha,
            message=str(commit_details.get("message") or "").strip(),
            committed_at=str(commit_author_payload.get("date") or ""),
            author_key=author_key,
            github_login=author_login,
            author_name=author_name,
            author_email=author_email,
            additions=int(stats.get("additions") or 0),
            deletions=int(stats.get("deletions") or 0),
        )

    async def _compute_divergence_days(self, owner: str, repo: str, base: str, head: str) -> int:
        comparison = await self.github_client.compare_refs(owner, repo, base, head)
        commits = comparison.get("commits") or []
        if not commits:
            return 0

        first_commit = commits[0]
        committed_at = _nested_value(first_commit, "commit", "author", "date")
        if not committed_at:
            return 0

        committed_dt = datetime.fromisoformat(committed_at.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        return max((now - committed_dt).days, 0)


def _nested_value(payload: dict, *keys: str) -> str | None:
    current = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    if current is None:
        return None
    value = str(current).strip()
    return value or None
