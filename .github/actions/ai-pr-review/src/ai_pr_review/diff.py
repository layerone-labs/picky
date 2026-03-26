from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import PurePosixPath
from typing import Iterable

from .config import (
    DEFAULT_EXCLUDE_PATTERNS,
    DEFAULT_GENERATED_PATTERNS,
    ReviewConfig,
)
from .models import ChangedFile, ReviewChunk


@dataclass(slots=True)
class DiffLine:
    kind: str
    text: str
    old_line: int | None
    new_line: int | None


@dataclass(slots=True)
class DiffHunk:
    header: str
    lines: list[DiffLine]
    old_start: int
    old_count: int
    new_start: int
    new_count: int

    @property
    def start_line(self) -> int | None:
        for line in self.lines:
            if line.new_line is not None:
                return line.new_line
        return None

    @property
    def end_line(self) -> int | None:
        values = [line.new_line for line in self.lines if line.new_line is not None]
        return max(values) if values else None

    def render(self) -> str:
        return "\n".join([self.header, *[line.text for line in self.lines]])


def is_binary_patch(file: ChangedFile) -> bool:
    if file.is_binary:
        return True
    patch = file.patch or ""
    return "\x00" in patch


def _path_matches(path: str, patterns: Iterable[str]) -> bool:
    posix = PurePosixPath(path).as_posix()
    for pattern in patterns:
        variants = [pattern]
        if pattern.startswith("**/"):
            variants.append(pattern[3:])
        for variant in variants:
            if fnmatchcase(posix, variant):
                return True
    return False


def is_generated_path(path: str, config: ReviewConfig) -> bool:
    patterns = [*DEFAULT_GENERATED_PATTERNS, *config.generated_paths]
    base = PurePosixPath(path).name.lower()
    if base in {
        "package-lock.json",
        "pnpm-lock.yaml",
        "yarn.lock",
        "cargo.lock",
        "poetry.lock",
        "go.sum",
    }:
        return True
    return _path_matches(path, patterns)


def should_include_file(file: ChangedFile, config: ReviewConfig) -> bool:
    if is_binary_patch(file) or is_generated_path(file.path, config):
        return False
    if config.include_paths and not _path_matches(file.path, config.include_paths):
        return False
    patterns = [*DEFAULT_EXCLUDE_PATTERNS, *config.exclude_paths]
    return not _path_matches(file.path, patterns)


def parse_unified_diff(patch: str) -> list[DiffHunk]:
    hunks: list[DiffHunk] = []
    current_header: str | None = None
    current_lines: list[DiffLine] = []
    old_line = new_line = None
    old_start = old_count = new_start = new_count = 0

    for raw_line in patch.splitlines():
        if raw_line.startswith("@@"):
            if current_header is not None:
                hunks.append(
                    DiffHunk(
                        header=current_header,
                        lines=current_lines,
                        old_start=old_start,
                        old_count=old_count,
                        new_start=new_start,
                        new_count=new_count,
                    )
                )
            current_header = raw_line
            current_lines = []
            header = raw_line.split("@@")[1].strip()
            old_part, new_part = header.split(" ", 1)
            old_start, old_count = _parse_hunk_range(old_part)
            new_start, new_count = _parse_hunk_range(new_part)
            old_line = old_start
            new_line = new_start
            continue
        if current_header is None:
            continue
        if raw_line.startswith("+") and not raw_line.startswith("+++"):
            current_lines.append(DiffLine("+", raw_line, None, new_line))
            new_line = (new_line or 0) + 1
        elif raw_line.startswith("-") and not raw_line.startswith("---"):
            current_lines.append(DiffLine("-", raw_line, old_line, None))
            old_line = (old_line or 0) + 1
        else:
            current_lines.append(DiffLine(" ", raw_line, old_line, new_line))
            old_line = (old_line or 0) + 1
            new_line = (new_line or 0) + 1

    if current_header is not None:
        hunks.append(
            DiffHunk(
                header=current_header,
                lines=current_lines,
                old_start=old_start,
                old_count=old_count,
                new_start=new_start,
                new_count=new_count,
            )
        )
    return hunks


def _parse_hunk_range(part: str) -> tuple[int, int]:
    cleaned = part.lstrip("-+")
    if "," in cleaned:
        start, count = cleaned.split(",", 1)
        return int(start), int(count)
    return int(cleaned), 1


def chunk_patch(file: ChangedFile, max_chars: int) -> list[ReviewChunk]:
    patch = file.patch or ""
    if len(patch) <= max_chars:
        if not patch.strip():
            return []
        return [ReviewChunk(file_path=file.path, patch=patch)]

    chunks: list[ReviewChunk] = []
    hunks = parse_unified_diff(patch)
    current_hunks: list[DiffHunk] = []
    current_len = 0

    for hunk in hunks:
        rendered = hunk.render()
        if len(rendered) > max_chars:
            if current_hunks:
                combined = "\n".join(h.render() for h in current_hunks)
                chunks.append(
                    ReviewChunk(
                        file_path=file.path,
                        patch=combined,
                        start_line=current_hunks[0].start_line,
                        end_line=current_hunks[-1].end_line,
                        original_patch=patch,
                    )
                )
                current_hunks = []
                current_len = 0
            chunks.append(
                ReviewChunk(
                    file_path=file.path,
                    patch=rendered,
                    start_line=hunk.start_line,
                    end_line=hunk.end_line,
                    original_patch=patch,
                )
            )
            continue
        if current_hunks and current_len + len(rendered) > max_chars:
            combined = "\n".join(h.render() for h in current_hunks)
            chunks.append(
                ReviewChunk(
                    file_path=file.path,
                    patch=combined,
                    start_line=current_hunks[0].start_line,
                    end_line=current_hunks[-1].end_line,
                    original_patch=patch,
                )
            )
            current_hunks = []
            current_len = 0
        current_hunks.append(hunk)
        current_len += len(rendered) + 1

    if current_hunks:
        combined = "\n".join(h.render() for h in current_hunks)
        chunks.append(
            ReviewChunk(
                file_path=file.path,
                patch=combined,
                start_line=current_hunks[0].start_line,
                end_line=current_hunks[-1].end_line,
                original_patch=patch,
            )
        )
    return chunks


def build_review_chunks(files: list[ChangedFile], max_chars: int) -> list[ReviewChunk]:
    chunks: list[ReviewChunk] = []
    for file in files:
        chunks.extend(chunk_patch(file, max_chars))
    return chunks
