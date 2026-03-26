from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from ._path import ACTION_SRC  # noqa: F401

from ai_pr_review.config import ReviewConfig
from ai_pr_review.models import ChangedFile, PullRequestInfo, RepoContextFile
from ai_pr_review.orchestrator import normalize_findings, run_review


class FakeProvider:
    def __init__(self, response: str) -> None:
        self.response = response
        self.prompts: list[object] = []

    def review(self, prompt):
        self.prompts.append(prompt)
        return self.response


class FakeClient:
    def __init__(self, files: list[ChangedFile], context: dict[str, str] | None = None) -> None:
        self.files = files
        self.context = context or {}
        self.requested_files: list[str] = []

    def list_pull_files(self, number: int):
        return list(self.files)

    def get_repo_file(self, path: str, ref: str):
        self.requested_files.append(path)
        if path not in self.context:
            return None
        return RepoContextFile(path=path, content=self.context[path])


class OrchestratorTests(unittest.TestCase):
    def test_normalize_findings_accepts_wrapped_json_and_strings(self) -> None:
        payload = {
            "findings": [
                {
                    "path": "src/app.py",
                    "line": "12",
                    "severity": "Medium",
                    "confidence": "0.8",
                    "title": "Missing guard",
                    "body": "This branch is unsafe.",
                    "suggested_fix": "Add a guard.",
                }
            ]
        }
        findings = normalize_findings(payload, "src/app.py")
        self.assertEqual(1, len(findings))
        self.assertEqual(12, findings[0].line)
        self.assertEqual("medium", findings[0].severity)
        self.assertTrue(findings[0].fingerprint)

    def test_run_review_uses_chunks_and_repo_context(self) -> None:
        patch_text = """@@ -1,2 +1,3 @@
 line-1
+line-2
+line-3
@@ -20,1 +21,2 @@
-old
+new
+newer
"""
        files = [ChangedFile(path="src/app.py", status="modified", patch=patch_text)]
        fake_client = FakeClient(files, context={"README.md": "repo guidance"})
        response = json.dumps(
            {
                "findings": [
                    {
                        "path": "src/app.py",
                        "line": 2,
                        "severity": "high",
                        "confidence": 0.91,
                        "title": "Unsafe change",
                        "body": "The new branch is unsafe.",
                        "suggested_fix": "Refactor the branch.",
                    }
                ]
            }
        )
        config = ReviewConfig(max_files=5, max_patch_chars=25, context_files=["README.md"])
        pr = PullRequestInfo(number=1, title="Update logic", body="body", head_sha="abc123")

        fake_provider = FakeProvider(response)
        with patch("ai_pr_review.orchestrator._provider_for", return_value=fake_provider):
            result = run_review(
                client=fake_client,
                pr_number=1,
                pr=pr,
                config=config,
                provider_name="openai",
                api_key="secret",
                model="gpt-test",
            )

        self.assertEqual(1, result.files_reviewed)
        self.assertGreaterEqual(result.chunks_reviewed, 1)
        self.assertEqual(1, len(result.findings))
        self.assertEqual("src/app.py", result.findings[0].path)
        self.assertEqual(2, len(fake_provider.prompts))
        self.assertIn("repo guidance", fake_provider.prompts[0].repo_context[0].content)
        self.assertIn("README.md", fake_client.requested_files)


if __name__ == "__main__":
    unittest.main()
