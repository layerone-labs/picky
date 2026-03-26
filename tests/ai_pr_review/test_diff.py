from __future__ import annotations

import unittest

from ._path import ACTION_SRC  # noqa: F401

from ai_pr_review.config import ReviewConfig
from ai_pr_review.diff import chunk_patch, parse_unified_diff, should_include_file
from ai_pr_review.models import ChangedFile


class DiffTests(unittest.TestCase):
    def test_parse_unified_diff_tracks_line_numbers(self) -> None:
        patch = """@@ -1,3 +1,4 @@
 context
-old
+new
 kept
"""
        hunks = parse_unified_diff(patch)
        self.assertEqual(1, len(hunks))
        self.assertEqual(1, hunks[0].start_line)
        self.assertEqual(3, hunks[0].end_line)
        additions = [line for line in hunks[0].lines if line.kind == "+"]
        self.assertEqual(2, additions[0].new_line)

    def test_chunk_patch_splits_on_hunks(self) -> None:
        patch = """@@ -1,1 +1,1 @@
-old-a
+new-a
@@ -10,1 +10,1 @@
-old-b
+new-b
"""
        file = ChangedFile(path="src/app.py", status="modified", patch=patch)
        chunks = chunk_patch(file, max_chars=35)
        self.assertEqual(2, len(chunks))
        self.assertEqual("src/app.py", chunks[0].file_path)
        self.assertIsNotNone(chunks[0].start_line)
        self.assertIsNotNone(chunks[1].start_line)

    def test_should_include_file_respects_generated_and_binary_filters(self) -> None:
        config = ReviewConfig(exclude_paths=["**/migrations/**"])
        generated = ChangedFile(path="dist/main.js", status="modified", patch="@@ -1 +1 @@\n-old\n+new\n")
        binary = ChangedFile(path="logo.png", status="modified", is_binary=True)
        excluded = ChangedFile(path="app/migrations/0001_init.py", status="modified", patch="@@ -1 +1 @@\n-old\n+new\n")
        include = ChangedFile(path="app/core.py", status="modified", patch="@@ -1 +1 @@\n-old\n+new\n")
        self.assertFalse(should_include_file(generated, config))
        self.assertFalse(should_include_file(binary, config))
        self.assertFalse(should_include_file(excluded, config))
        self.assertTrue(should_include_file(include, config))


if __name__ == "__main__":
    unittest.main()
