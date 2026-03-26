from __future__ import annotations

import hashlib
from dataclasses import dataclass

from .github_client import GitHubClient, GitHubComment
from .models import Finding, SEVERITY_ORDER

FINGERPRINT_PREFIX = "<!-- ai-pr-review:"


@dataclass(slots=True)
class PublishResult:
    posted_inline: int = 0
    posted_summary: bool = False
    skipped_duplicate: int = 0


def finding_fingerprint(finding: Finding) -> str:
    raw = "|".join(
        [
            finding.path.strip().lower(),
            str(finding.line or ""),
            finding.severity.strip().lower(),
            f"{finding.confidence:.3f}",
            finding.title.strip(),
            finding.body.strip(),
            finding.suggested_fix.strip(),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def with_fingerprint(finding: Finding) -> Finding:
    fp = finding.fingerprint or finding_fingerprint(finding)
    return Finding(
        path=finding.path,
        line=finding.line,
        severity=finding.severity,
        confidence=finding.confidence,
        title=finding.title,
        body=finding.body,
        suggested_fix=finding.suggested_fix,
        fingerprint=fp,
    )


def _marker(fingerprint: str) -> str:
    return f"{FINGERPRINT_PREFIX}fingerprint={fingerprint} -->"


def build_inline_comment(finding: Finding) -> str:
    finding = with_fingerprint(finding)
    parts = [f"**Picky [{finding.severity}]** {finding.title}", "", finding.body]
    if finding.suggested_fix:
        parts.extend(["", f"Suggested fix: {finding.suggested_fix}"])
    parts.extend(["", _marker(finding.fingerprint)])
    return "\n".join(parts)


def build_summary_comment(findings: list[Finding], pr_title: str) -> str:
    counts = {severity: 0 for severity in SEVERITY_ORDER}
    for finding in findings:
        counts[finding.severity] = counts.get(finding.severity, 0) + 1
    header = [
        "## Picky",
        "",
        f"Review for: {pr_title}",
        "",
        f"Findings: {len(findings)}",
        f"- high: {counts.get('high', 0)}",
        f"- medium: {counts.get('medium', 0)}",
        f"- low: {counts.get('low', 0)}",
        "",
    ]
    for finding in findings:
        finding = with_fingerprint(finding)
        header.extend(
            [
                f"### {finding.title} ({finding.severity})",
                f"- Path: `{finding.path}`",
                f"- Line: `{finding.line}`" if finding.line is not None else "- Line: n/a",
                f"- Confidence: `{finding.confidence:.2f}`",
                finding.body,
            ]
        )
        if finding.suggested_fix:
            header.extend(["", f"Suggested fix: {finding.suggested_fix}"])
        header.extend(["", _marker(finding.fingerprint), ""])
    return "\n".join(header).strip()


def build_review_payload_comment(finding: Finding) -> dict[str, str | int]:
    return {
        "path": finding.path,
        "line": int(finding.line or 0),
        "side": "RIGHT",
        "body": build_inline_comment(finding),
    }


def extract_fingerprint(body: str) -> str | None:
    if FINGERPRINT_PREFIX not in body:
        return None
    for part in body.split(FINGERPRINT_PREFIX, 1)[1].split("-->", 1)[0].split():
        if part.startswith("fingerprint="):
            return part.split("=", 1)[1].strip()
    return None


def dedupe_against_existing(findings: list[Finding], comments: list[GitHubComment]) -> list[Finding]:
    existing = {fp for fp in (extract_fingerprint(c.body) for c in comments) if fp}
    result: list[Finding] = []
    for finding in findings:
        fp = finding.fingerprint or finding_fingerprint(finding)
        if fp in existing:
            continue
        result.append(with_fingerprint(finding))
    return result


def publish(
    client: GitHubClient,
    pr_number: int,
    commit_id: str | None,
    findings: list[Finding],
    pr_title: str,
    post_summary: bool,
    min_severity_to_publish: str,
) -> PublishResult:
    result = PublishResult()
    threshold = SEVERITY_ORDER[min_severity_to_publish]
    publishable = [f for f in findings if SEVERITY_ORDER.get(f.severity, 0) >= threshold]
    existing_review_comments = client.list_review_comments(pr_number)
    existing_issue_comments = client.list_issue_comments(pr_number)
    existing_comments = [*existing_review_comments, *existing_issue_comments]
    publishable = dedupe_against_existing(publishable, existing_comments)

    inline_findings = [
        finding for finding in publishable if finding.line is not None and finding.path and commit_id
    ]
    summary_findings = [finding for finding in publishable if finding not in inline_findings]
    inline_count = len(inline_findings)

    if inline_findings and commit_id:
        review_body = build_summary_comment(publishable, pr_title) if post_summary else "## AI PR Review"
        if not post_summary:
            review_body = "## Picky"
        try:
            client.create_pull_review(
                pr_number,
                commit_id,
                review_body,
                [build_review_payload_comment(finding) for finding in inline_findings],
            )
            result.posted_inline = inline_count
            result.posted_summary = post_summary
        except Exception:
            client.create_issue_comment(pr_number, build_summary_comment(publishable, pr_title))
            result.posted_summary = True
            result.posted_inline = 0
    elif publishable and post_summary:
        client.create_issue_comment(pr_number, build_summary_comment(publishable, pr_title))
        result.posted_summary = True
        result.posted_inline = 0
    elif summary_findings and not post_summary:
        result.posted_inline = 0

    result.skipped_duplicate = len(findings) - len(publishable)
    return result
