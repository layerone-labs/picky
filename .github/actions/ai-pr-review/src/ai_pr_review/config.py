from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:  # pragma: no cover - exercised implicitly when installed
    import yaml
except ModuleNotFoundError:  # pragma: no cover - fallback for local tests
    yaml = None

from .models import SEVERITY_ORDER

DEFAULT_EXCLUDE_PATTERNS: list[str] = [
    "**/node_modules/**",
    "**/dist/**",
    "**/build/**",
    "**/coverage/**",
    "**/.venv/**",
    "**/vendor/**",
]
DEFAULT_GENERATED_PATTERNS: list[str] = [
    "**/*.generated.*",
    "**/*.gen.*",
    "**/*.min.*",
    "**/*.map",
    "**/*.snap",
]
DEFAULT_CONTEXT_FILES: list[str] = [
    "README.md",
    "CONTRIBUTING.md",
    "CODEOWNERS",
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "setup.cfg",
    "setup.py",
    "Cargo.toml",
    "go.mod",
    "tsconfig.json",
    "eslint.config.js",
    ".eslintrc",
    ".github/copilot-instructions.md",
]


@dataclass(slots=True)
class ReviewConfig:
    include_paths: list[str] = field(default_factory=list)
    exclude_paths: list[str] = field(default_factory=list)
    generated_paths: list[str] = field(default_factory=list)
    context_files: list[str] = field(default_factory=lambda: list(DEFAULT_CONTEXT_FILES))
    prompt_extensions: str = ""
    max_files: int = 20
    max_patch_chars: int = 24000
    post_summary: bool = True
    min_severity_to_publish: str = "low"


def _as_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def _as_int(value: Any, default: int) -> int:
    if value is None:
        return default
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _split_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [line.strip() for line in value.splitlines() if line.strip()]
    return [str(value).strip()]


def _coerce_scalar(value: str) -> Any:
    text = value.strip()
    if not text:
        return ""
    if text.startswith(("'", '"')) and text.endswith(("'", '"')) and len(text) >= 2:
        return text[1:-1]
    lower = text.lower()
    if lower in {"true", "false"}:
        return lower == "true"
    if lower in {"null", "none", "~"}:
        return None
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        return text


def _indent_width(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _fallback_yaml_load(text: str) -> dict[str, Any]:
    lines = text.splitlines()

    def next_meaningful(index: int) -> tuple[int | None, str | None]:
        j = index
        while j < len(lines):
            raw = lines[j]
            stripped = raw.strip()
            if not stripped or stripped.startswith("#"):
                j += 1
                continue
            return j, raw
        return None, None

    def parse_list(index: int, min_indent: int) -> tuple[list[Any], int]:
        items: list[Any] = []
        i = index
        while i < len(lines):
            raw = lines[i]
            stripped = raw.strip()
            if not stripped or stripped.startswith("#"):
                i += 1
                continue
            indent = _indent_width(raw)
            if indent < min_indent:
                break
            if indent > min_indent:
                i += 1
                continue
            if not stripped.startswith("- "):
                break
            items.append(_coerce_scalar(stripped[2:]))
            i += 1
        return items, i

    def parse_block(index: int, min_indent: int) -> tuple[dict[str, Any], int]:
        result: dict[str, Any] = {}
        i = index
        while i < len(lines):
            raw = lines[i]
            stripped = raw.strip()
            if not stripped or stripped.startswith("#"):
                i += 1
                continue
            indent = _indent_width(raw)
            if indent < min_indent:
                break
            if stripped.startswith("- "):
                break
            if ":" not in stripped:
                i += 1
                continue
            key, rest = stripped.split(":", 1)
            key = key.strip()
            value = rest.strip()
            if value == "|":
                block: list[str] = []
                i += 1
                while i < len(lines):
                    block_raw = lines[i]
                    block_stripped = block_raw.strip()
                    if not block_stripped:
                        block.append("")
                        i += 1
                        continue
                    block_indent = _indent_width(block_raw)
                    if block_indent <= indent:
                        break
                    block.append(block_raw[block_indent:].rstrip())
                    i += 1
                result[key] = "\n".join(block).rstrip()
                continue
            if value:
                result[key] = _coerce_scalar(value)
                i += 1
                continue
            next_index, next_raw = next_meaningful(i + 1)
            if next_raw is None:
                result[key] = {}
                i += 1
                continue
            next_indent = _indent_width(next_raw)
            if next_indent <= indent:
                result[key] = {}
                i += 1
                continue
            if next_raw.strip().startswith("- "):
                child, new_i = parse_list(next_index, next_indent)
            else:
                child, new_i = parse_block(next_index, next_indent)
            result[key] = child
            i = new_i
        return result, i

    parsed, _ = parse_block(0, 0)
    return parsed


def _normalize_schema(raw: dict[str, Any]) -> dict[str, Any]:
    if "review" in raw and isinstance(raw["review"], dict):
        review = raw["review"]
    else:
        review = raw
    if not isinstance(review, dict):
        return {}
    return review


def load_review_config(
    repo_root: Path,
    config_path: str | None,
    inputs: dict[str, Any] | None = None,
) -> ReviewConfig:
    inputs = inputs or {}
    config = ReviewConfig(
        max_files=_as_int(inputs.get("max_files"), 20),
        max_patch_chars=_as_int(inputs.get("max_patch_chars"), 24000),
        post_summary=_as_bool(inputs.get("post_summary"), True),
        min_severity_to_publish=str(inputs.get("min_severity_to_publish", "low")).strip().lower(),
    )

    if config_path:
        path = Path(config_path)
        if not path.is_absolute():
            path = repo_root / path
        if path.exists():
            text = path.read_text(encoding="utf-8")
            if yaml is not None:
                raw = yaml.safe_load(text) or {}
            else:
                raw = _fallback_yaml_load(text)
            if isinstance(raw, dict):
                review = _normalize_schema(raw)
                paths = review.get("paths") if isinstance(review.get("paths"), dict) else {}
                generated = review.get("generated") if isinstance(review.get("generated"), dict) else {}
                limits = review.get("limits") if isinstance(review.get("limits"), dict) else {}
                reporting = review.get("reporting") if isinstance(review.get("reporting"), dict) else {}
                prompt = review.get("prompt") if isinstance(review.get("prompt"), dict) else {}

                config.include_paths = _split_list(
                    paths.get("include")
                    or paths.get("include_paths")
                    or review.get("include_paths")
                    or review.get("include")
                )
                config.exclude_paths = _split_list(
                    paths.get("exclude")
                    or paths.get("exclude_paths")
                    or review.get("exclude_paths")
                    or review.get("exclude")
                )
                config.generated_paths = _split_list(
                    generated.get("exclude")
                    or generated.get("paths")
                    or review.get("generated_paths")
                    or review.get("generated")
                    or review.get("skip_paths")
                )
                config.context_files = _split_list(review.get("context_files")) or config.context_files
                extensions = prompt.get("extensions") if isinstance(prompt.get("extensions"), list) else prompt.get("extensions")
                if extensions is None:
                    extensions = review.get("prompt_extensions") or review.get("prompt")
                if isinstance(extensions, list):
                    config.prompt_extensions = "\n".join(
                        str(item).strip() for item in extensions if str(item).strip()
                    )
                else:
                    config.prompt_extensions = str(extensions or "").strip()
                config.max_files = _as_int(limits.get("max_files") or review.get("max_files"), config.max_files)
                config.max_patch_chars = _as_int(
                    limits.get("max_patch_chars") or review.get("max_patch_chars"),
                    config.max_patch_chars,
                )
                if "post_summary" in reporting:
                    config.post_summary = _as_bool(reporting.get("post_summary"), config.post_summary)
                elif "post_summary" in review:
                    config.post_summary = _as_bool(review.get("post_summary"), config.post_summary)
                if "min_severity" in reporting:
                    config.min_severity_to_publish = str(reporting.get("min_severity")).strip().lower()
                else:
                    config.min_severity_to_publish = str(
                        review.get("min_severity_to_publish", config.min_severity_to_publish)
                    ).strip().lower()

    if inputs.get("max_files") is not None:
        config.max_files = _as_int(inputs.get("max_files"), config.max_files)
    if inputs.get("max_patch_chars") is not None:
        config.max_patch_chars = _as_int(inputs.get("max_patch_chars"), config.max_patch_chars)
    if inputs.get("post_summary") is not None:
        config.post_summary = _as_bool(inputs.get("post_summary"), config.post_summary)
    if inputs.get("min_severity_to_publish") is not None:
        config.min_severity_to_publish = str(inputs.get("min_severity_to_publish")).strip().lower()

    if config.min_severity_to_publish not in SEVERITY_ORDER:
        config.min_severity_to_publish = "low"

    return config
