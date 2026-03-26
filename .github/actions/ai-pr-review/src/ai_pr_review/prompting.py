from __future__ import annotations

from textwrap import indent

from .config import ReviewConfig
from .models import RepoContextFile, ReviewChunk


SYSTEM_PROMPT = """You are an expert GitHub code reviewer.
Focus on correctness, regressions, security, data loss, concurrency, API misuse, missing tests, and maintainability.
Ignore style nits unless they hide a bug or meaningful risk.
Use only evidence from the provided diff and repo context.

Return JSON only in this exact shape:
{"findings":[{"path":"relative/path","line":123,"severity":"low|medium|high","confidence":0.0,"title":"short title","body":"detailed explanation","suggested_fix":"optional fix suggestion"}]}

Rules:
- Use the changed file path from the diff.
- Use the most relevant current-file line number when anchoring a finding.
- If no line anchor is appropriate, omit the finding rather than guessing.
- Return an empty findings array when nothing actionable is found.
"""


def build_policy_summary(config: ReviewConfig) -> str:
    lines = [
        "Review policy:",
        f"- include_paths: {config.include_paths or ['<all>']}",
        f"- exclude_paths: {config.exclude_paths or ['<default excludes>']}",
        f"- generated_paths: {config.generated_paths or ['<default generated heuristics>']}",
        f"- max_files: {config.max_files}",
        f"- max_patch_chars: {config.max_patch_chars}",
        f"- min_severity_to_publish: {config.min_severity_to_publish}",
        f"- post_summary: {config.post_summary}",
    ]
    if config.prompt_extensions:
        lines.extend(["- repo guidance:", indent(config.prompt_extensions, "  ")])
    return "\n".join(lines)


def build_prompt(
    pr_title: str,
    pr_body: str | None,
    chunk: ReviewChunk,
    repo_context: list[RepoContextFile],
    policy_summary: str,
) -> str:
    sections = [
        f"Pull request title: {pr_title}",
        f"Pull request body: {pr_body or '<none>'}",
        f"Changed file: {chunk.file_path}",
        f"Line window: {chunk.start_line or 'n/a'}-{chunk.end_line or 'n/a'}",
        "Patch:",
        chunk.patch,
    ]
    if repo_context:
        context_blocks = []
        for ctx in repo_context:
            context_blocks.append(f"### {ctx.path}\n{ctx.content}")
        sections.extend(["Repository context:", "\n\n".join(context_blocks)])
    sections.extend(["Policy summary:", policy_summary])
    sections.append(
        "Return JSON only. Do not wrap it in markdown fences. Do not include commentary outside JSON."
    )
    return "\n\n".join(sections)
