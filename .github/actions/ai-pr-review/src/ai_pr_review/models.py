from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


SEVERITY_ORDER = {"low": 1, "medium": 2, "high": 3}


@dataclass(slots=True)
class PullRequestInfo:
    number: int
    title: str
    body: str | None = None
    head_sha: str | None = None
    base_sha: str | None = None
    html_url: str | None = None


@dataclass(slots=True)
class ChangedFile:
    path: str
    status: str
    additions: int = 0
    deletions: int = 0
    changes: int = 0
    patch: str | None = None
    raw_url: str | None = None
    blob_url: str | None = None
    is_binary: bool = False
    is_generated: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RepoContextFile:
    path: str
    content: str


@dataclass(slots=True)
class ReviewChunk:
    file_path: str
    patch: str
    start_line: int | None = None
    end_line: int | None = None
    original_patch: str | None = None


@dataclass(slots=True)
class ReviewPrompt:
    pr: PullRequestInfo
    chunk: ReviewChunk
    repo_context: list[RepoContextFile]
    policy_summary: str
    model: str


@dataclass(slots=True)
class Finding:
    path: str
    line: int | None
    severity: str
    confidence: float
    title: str
    body: str
    suggested_fix: str = ""
    fingerprint: str = ""

    def normalized(self) -> "Finding":
        return Finding(
            path=self.path.strip(),
            line=self.line,
            severity=self.severity.strip().lower(),
            confidence=max(0.0, min(1.0, float(self.confidence))),
            title=self.title.strip(),
            body=self.body.strip(),
            suggested_fix=self.suggested_fix.strip(),
            fingerprint=self.fingerprint.strip(),
        )
