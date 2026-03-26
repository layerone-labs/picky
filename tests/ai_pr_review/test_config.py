from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ._path import ACTION_SRC  # noqa: F401

from ai_pr_review.config import load_review_config


class ConfigTests(unittest.TestCase):
    def test_nested_review_schema_is_supported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            config_path = repo_root / ".ai-code-review.yml"
            config_path.write_text(
                """
version: 1

review:
  paths:
    include:
      - "**/*.py"
      - "**/*.js"
    exclude:
      - "**/dist/**"
  generated:
    exclude:
      - "**/*.generated.*"
      - "**/*.snap"
  limits:
    max_files: 25
    max_patch_chars: 120000
  reporting:
    min_severity: medium
  prompt:
    extensions:
      - "First guidance"
      - "Second guidance"
""".strip()
                + "\n",
                encoding="utf-8",
            )

            config = load_review_config(repo_root, ".ai-code-review.yml", {})

        self.assertEqual(["**/*.py", "**/*.js"], config.include_paths)
        self.assertEqual(["**/dist/**"], config.exclude_paths)
        self.assertEqual(["**/*.generated.*", "**/*.snap"], config.generated_paths)
        self.assertEqual(25, config.max_files)
        self.assertEqual(120000, config.max_patch_chars)
        self.assertEqual("medium", config.min_severity_to_publish)
        self.assertIn("First guidance", config.prompt_extensions)
        self.assertIn("Second guidance", config.prompt_extensions)


if __name__ == "__main__":
    unittest.main()
