from __future__ import annotations

import unittest

from ._path import ACTION_SRC  # noqa: F401

from ai_pr_review.github_client import GitHubComment
from ai_pr_review.models import Finding
from ai_pr_review.publisher import (
    build_inline_comment,
    build_summary_comment,
    dedupe_against_existing,
    extract_fingerprint,
    finding_fingerprint,
    publish,
)


class FakeClient:
    def __init__(self, existing: list[GitHubComment] | None = None) -> None:
        self.existing = existing or []
        self.inline_calls: list[tuple[int, str, str, int, str]] = []
        self.issue_calls: list[tuple[int, str]] = []

    def list_review_comments(self, number: int):
        return list(self.existing)

    def list_issue_comments(self, number: int):
        return []

    def create_review_comment(self, number: int, body: str, path: str, line: int, commit_id: str):
        self.inline_calls.append((number, body, path, line, commit_id))

    def create_issue_comment(self, number: int, body: str):
        self.issue_calls.append((number, body))


class PublisherTests(unittest.TestCase):
    def test_fingerprint_marker_round_trips(self) -> None:
        finding = Finding(
            path="src/app.py",
            line=8,
            severity="medium",
            confidence=0.7,
            title="Title",
            body="Body",
            suggested_fix="Fix",
        )
        body = build_inline_comment(finding)
        fp = extract_fingerprint(body)
        self.assertEqual(finding_fingerprint(finding), fp)

    def test_dedupe_skips_existing_comment_fingerprints(self) -> None:
        finding = Finding(
            path="src/app.py",
            line=8,
            severity="medium",
            confidence=0.7,
            title="Title",
            body="Body",
            suggested_fix="Fix",
        )
        existing = [GitHubComment(id=1, body=build_inline_comment(finding))]
        deduped = dedupe_against_existing([finding], existing)
        self.assertEqual([], deduped)

    def test_publish_posts_inline_and_summary(self) -> None:
        finding = Finding(
            path="src/app.py",
            line=8,
            severity="high",
            confidence=0.9,
            title="Unsafe branch",
            body="The new branch is unsafe.",
            suggested_fix="Add a guard.",
        )
        client = FakeClient()
        result = publish(
            client=client,
            pr_number=12,
            commit_id="sha123",
            findings=[finding],
            pr_title="Update logic",
            post_summary=True,
            min_severity_to_publish="low",
        )
        self.assertEqual(1, result.posted_inline)
        self.assertTrue(result.posted_summary)
        self.assertEqual(1, len(client.inline_calls))
        self.assertEqual(1, len(client.issue_calls))
        self.assertIn("AI PR Review", build_summary_comment([finding], "Update logic"))


if __name__ == "__main__":
    unittest.main()
