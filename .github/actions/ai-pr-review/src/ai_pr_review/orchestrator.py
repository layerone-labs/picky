from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .config import ReviewConfig
from .diff import build_review_chunks, should_include_file
from .github_client import GitHubClient
from .models import Finding, RepoContextFile, ReviewPrompt
from .prompting import build_policy_summary
from .providers import OpenAIProvider, ProviderAdapter, UnsupportedProvider
from .publisher import finding_fingerprint


@dataclass(slots=True)
class ReviewRunResult:
    findings: list[Finding]
    chunks_reviewed: int
    files_reviewed: int
    files_skipped: int


def _provider_for(name: str, api_key: str, model: str) -> ProviderAdapter:
    if name.lower() == "openai":
        return OpenAIProvider(api_key=api_key, model=model)
    return UnsupportedProvider(name)


def _extract_json(text: str) -> Any:
    candidate = text.strip()
    if "```" in candidate:
        parts = candidate.split("```")
        for part in parts:
            stripped = part.strip()
            if stripped.startswith("json"):
                candidate = stripped[4:].strip()
                break
            if stripped.startswith("{") or stripped.startswith("["):
                candidate = stripped
                break
    if candidate.startswith("```") and candidate.endswith("```"):
        candidate = candidate[3:-3].strip()
    return json.loads(candidate)


def normalize_findings(payload: Any, default_path: str) -> list[Finding]:
    if isinstance(payload, dict):
        items = payload.get("findings", [])
    else:
        items = payload
    findings: list[Finding] = []
    if not isinstance(items, list):
        return findings
    for item in items:
        if not isinstance(item, dict):
            continue
        line_value = item.get("line")
        if isinstance(line_value, str) and line_value.strip():
            try:
                line_value = int(line_value.strip())
            except ValueError:
                line_value = None
        elif not isinstance(line_value, int):
            line_value = None
        finding = Finding(
            path=str(item.get("path") or default_path),
            line=line_value,
            severity=str(item.get("severity", "low")).strip().lower(),
            confidence=float(item.get("confidence", 0.5) or 0.5),
            title=str(item.get("title", "")).strip(),
            body=str(item.get("body", "")).strip(),
            suggested_fix=str(item.get("suggested_fix", "")).strip(),
        ).normalized()
        if not finding.title or not finding.body:
            continue
        finding.fingerprint = finding_fingerprint(finding)
        findings.append(finding)
    return findings


def _load_repo_context(client: GitHubClient, config: ReviewConfig, ref: str | None) -> list[RepoContextFile]:
    context: list[RepoContextFile] = []
    if not ref:
        return context
    for path in config.context_files:
        try:
            item = client.get_repo_file(path, ref)
        except Exception:
            item = None
        if item is not None:
            context.append(item)
    return context


def run_review(
    *,
    client: GitHubClient,
    pr_number: int,
    pr: Any,
    config: ReviewConfig,
    provider_name: str,
    api_key: str,
    model: str,
) -> ReviewRunResult:
    provider = _provider_for(provider_name, api_key, model)
    files = client.list_pull_files(pr_number)
    filtered = [file for file in files if should_include_file(file, config)]
    filtered = filtered[: config.max_files]
    repo_context = _load_repo_context(client, config, getattr(pr, "head_sha", None))
    chunks = build_review_chunks(filtered, config.max_patch_chars)
    policy_summary = build_policy_summary(config)

    findings: list[Finding] = []
    for chunk in chunks:
        prompt = ReviewPrompt(
            pr=pr,
            chunk=chunk,
            repo_context=repo_context,
            policy_summary=policy_summary,
            model=model,
        )
        raw = provider.review(prompt)
        try:
            payload = _extract_json(raw)
        except Exception:
            continue
        findings.extend(normalize_findings(payload, chunk.file_path))

    unique: list[Finding] = []
    seen: set[str] = set()
    for finding in findings:
        if finding.fingerprint in seen:
            continue
        seen.add(finding.fingerprint)
        unique.append(finding)

    return ReviewRunResult(
        findings=unique,
        chunks_reviewed=len(chunks),
        files_reviewed=len(filtered),
        files_skipped=max(0, len(files) - len(filtered)),
    )
