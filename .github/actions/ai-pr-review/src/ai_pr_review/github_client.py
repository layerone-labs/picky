from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

from .models import ChangedFile, PullRequestInfo, RepoContextFile


@dataclass(slots=True)
class GitHubComment:
    id: int
    body: str
    path: str | None = None
    line: int | None = None
    user_login: str | None = None
    url: str | None = None


class GitHubClient:
    def __init__(self, token: str, repository: str, api_base: str = "https://api.github.com") -> None:
        self._token = token
        self._repository = repository
        self._api_base = api_base.rstrip("/")

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            f"{self._api_base}{path}",
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "Content-Type": "application/json",
            },
        )
        try:
            with urlopen(request) as response:
                body = response.read().decode("utf-8")
                return json.loads(body) if body else None
        except HTTPError as exc:
            body = exc.read().decode("utf-8") if exc.fp else ""
            raise RuntimeError(f"GitHub API request failed: {method} {path}: {exc.code} {body}") from exc

    def get_pull_request(self, number: int) -> PullRequestInfo:
        data = self._request("GET", f"/repos/{self._repository}/pulls/{number}")
        return PullRequestInfo(
            number=number,
            title=data.get("title", ""),
            body=data.get("body"),
            head_sha=(data.get("head") or {}).get("sha"),
            base_sha=(data.get("base") or {}).get("sha"),
            html_url=data.get("html_url"),
        )

    def list_pull_files(self, number: int) -> list[ChangedFile]:
        files: list[ChangedFile] = []
        page = 1
        while True:
            data = self._request(
                "GET",
                f"/repos/{self._repository}/pulls/{number}/files?per_page=100&page={page}",
            )
            if not data:
                break
            for item in data:
                files.append(
                    ChangedFile(
                        path=item.get("filename", ""),
                        status=item.get("status", ""),
                        additions=item.get("additions", 0) or 0,
                        deletions=item.get("deletions", 0) or 0,
                        changes=item.get("changes", 0) or 0,
                        patch=item.get("patch"),
                        raw_url=item.get("raw_url"),
                        blob_url=item.get("blob_url"),
                        is_binary=not bool(item.get("patch")) and item.get("status") != "removed",
                        metadata=item,
                    )
                )
            if len(data) < 100:
                break
            page += 1
        return files

    def get_repo_file(self, path: str, ref: str) -> RepoContextFile | None:
        encoded_path = quote(path, safe="/")
        data = self._request(
            "GET",
            f"/repos/{self._repository}/contents/{encoded_path}?ref={quote(ref, safe='')}",
        )
        if not isinstance(data, dict):
            return None
        if data.get("encoding") != "base64" or "content" not in data:
            return None
        content = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
        return RepoContextFile(path=path, content=content)

    def list_review_comments(self, number: int) -> list[GitHubComment]:
        data = self._request("GET", f"/repos/{self._repository}/pulls/{number}/comments?per_page=100")
        comments: list[GitHubComment] = []
        for item in data or []:
            comments.append(
                GitHubComment(
                    id=item.get("id", 0),
                    body=item.get("body", ""),
                    path=item.get("path"),
                    line=item.get("line"),
                    user_login=(item.get("user") or {}).get("login"),
                    url=item.get("url"),
                )
            )
        return comments

    def list_issue_comments(self, number: int) -> list[GitHubComment]:
        data = self._request("GET", f"/repos/{self._repository}/issues/{number}/comments?per_page=100")
        comments: list[GitHubComment] = []
        for item in data or []:
            comments.append(
                GitHubComment(
                    id=item.get("id", 0),
                    body=item.get("body", ""),
                    user_login=(item.get("user") or {}).get("login"),
                    url=item.get("url"),
                )
            )
        return comments

    def create_review_comment(
        self, number: int, body: str, path: str, line: int, commit_id: str
    ) -> None:
        self._request(
            "POST",
            f"/repos/{self._repository}/pulls/{number}/comments",
            {
                "body": body,
                "commit_id": commit_id,
                "path": path,
                "line": line,
                "side": "RIGHT",
            },
        )

    def create_issue_comment(self, number: int, body: str) -> None:
        self._request(
            "POST",
            f"/repos/{self._repository}/issues/{number}/comments",
            {"body": body},
        )
