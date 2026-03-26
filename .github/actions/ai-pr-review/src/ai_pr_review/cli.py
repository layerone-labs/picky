from __future__ import annotations

import json
import os
from pathlib import Path

from .config import load_review_config
from .github_client import GitHubClient
from .orchestrator import run_review
from .publisher import publish
from .providers import resolve_provider_settings


def _read_event(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _input(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(f"INPUT_{name.upper()}")
    if value is None or value == "":
        return default
    return value


def main() -> int:
    token = os.environ.get("GITHUB_TOKEN", "")
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    event_path = os.environ.get("GITHUB_EVENT_PATH", "")
    if not token or not repository or not event_path:
        raise RuntimeError("GITHUB_TOKEN, GITHUB_REPOSITORY, and GITHUB_EVENT_PATH must be set")

    event = _read_event(event_path)
    pr = event.get("pull_request") or {}
    pr_number = int(pr.get("number") or event.get("number") or 0)
    if pr_number <= 0:
        raise RuntimeError("Could not determine pull request number from the GitHub event payload")

    repo_root = Path.cwd()
    config = load_review_config(
        repo_root,
        _input("config_path", ".ai-code-review.yml"),
        {
            "max_files": _input("max_files", "20"),
            "max_patch_chars": _input("max_patch_chars", "24000"),
            "post_summary": _input("post_summary", "true"),
            "min_severity_to_publish": _input("min_severity_to_publish", "low"),
        },
    )
    client = GitHubClient(token=token, repository=repository)
    pr_info = client.get_pull_request(pr_number)
    provider_settings = resolve_provider_settings(
        _input("provider", "deepseek") or "deepseek",
        api_key=_input("api_key"),
        model=_input("model"),
        base_url=_input("base_url"),
    )
    review = run_review(
        client=client,
        pr_number=pr_number,
        pr=pr_info,
        config=config,
        provider_settings=provider_settings,
    )
    publish(
        client=client,
        pr_number=pr_number,
        commit_id=pr_info.head_sha,
        findings=review.findings,
        pr_title=pr_info.title,
        post_summary=config.post_summary,
        min_severity_to_publish=config.min_severity_to_publish,
        review_language=config.review_language,
    )

    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        outputs = {
            "files_reviewed": review.files_reviewed,
            "chunks_reviewed": review.chunks_reviewed,
            "findings": len(review.findings),
        }
        with Path(output_path).open("a", encoding="utf-8") as handle:
            for key, value in outputs.items():
                handle.write(f"{key}={value}\n")
    return 0
