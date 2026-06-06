from __future__ import annotations

import glob
import os
from dataclasses import dataclass
from pathlib import Path
import re


@dataclass(frozen=True)
class LogTail:
    path: str
    exists: bool
    size_bytes: int
    lines: list[str]
    truncated: bool
    error: str | None = None


def tail_text_file(path: str, max_lines: int = 200, max_bytes: int = 262_144) -> LogTail:
    safe_lines = max(1, int(max_lines))
    safe_bytes = max(1024, int(max_bytes))
    resolved_path = os.path.abspath(path)

    if not os.path.exists(resolved_path):
        return LogTail(path=resolved_path, exists=False, size_bytes=0, lines=[], truncated=False)
    if not os.path.isfile(resolved_path):
        return LogTail(path=resolved_path, exists=False, size_bytes=0, lines=[], truncated=False, error="Path is not a file.")

    try:
        size_bytes = os.path.getsize(resolved_path)
        read_size = min(size_bytes, safe_bytes)
        with open(resolved_path, "rb") as handle:
            handle.seek(max(0, size_bytes - read_size))
            raw = handle.read(read_size)
    except OSError as exc:
        return LogTail(path=resolved_path, exists=True, size_bytes=0, lines=[], truncated=False, error=str(exc))

    text = raw.decode("utf-8", errors="replace")
    lines = text.splitlines()
    if size_bytes > read_size and lines:
        lines = lines[1:]
    return LogTail(
        path=resolved_path,
        exists=True,
        size_bytes=size_bytes,
        lines=lines[-safe_lines:],
        truncated=size_bytes > read_size or len(lines) > safe_lines,
    )


def tail_recent_trace_logs(path: str, max_lines: int = 200, max_bytes: int = 262_144, max_files: int = 4) -> LogTail:
    safe_lines = max(1, int(max_lines))
    candidates = _recent_trace_log_paths(path, max_files=max_files)
    if not candidates:
        return tail_text_file(path, max_lines=max_lines, max_bytes=max_bytes)

    tails = [tail_text_file(candidate, max_lines=safe_lines, max_bytes=max_bytes) for candidate in candidates]
    existing = [tail for tail in tails if tail.exists]
    if not existing:
        return tails[0] if tails else tail_text_file(path, max_lines=max_lines, max_bytes=max_bytes)

    merged_lines: list[tuple[str, int, str]] = []
    for file_index, tail in enumerate(existing):
        for line_index, line in enumerate(tail.lines):
            merged_lines.append((_log_line_sort_key(line), file_index * 1_000_000 + line_index, line))
    merged_lines.sort(key=lambda item: (item[0], item[1]))

    visible_lines = [line for _, _, line in merged_lines[-safe_lines:]]
    paths = [tail.path for tail in existing]
    path_label = paths[0] if len(paths) == 1 else f"{paths[0]} (+{len(paths) - 1} files)"
    errors = [tail.error for tail in tails if tail.error]
    return LogTail(
        path=path_label,
        exists=True,
        size_bytes=sum(tail.size_bytes for tail in existing),
        lines=visible_lines,
        truncated=any(tail.truncated for tail in existing) or len(merged_lines) > safe_lines,
        error="; ".join(errors) if errors else None,
    )


def _recent_trace_log_paths(path: str, *, max_files: int) -> list[str]:
    resolved_path = Path(os.path.abspath(path))
    log_dir = resolved_path.parent
    configured_name = resolved_path.name
    prefix = configured_name.split(".")[0] or configured_name
    prefix = re.sub(r"_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}$", "", prefix)
    pattern = str(log_dir / f"{prefix}*.log*")
    files = [Path(candidate) for candidate in glob.glob(pattern)]
    files = [candidate for candidate in files if candidate.is_file()]
    if resolved_path.is_file() and resolved_path not in files:
        files.append(resolved_path)
    files.sort(key=lambda candidate: candidate.stat().st_mtime, reverse=True)
    return [str(candidate) for candidate in files[: max(1, int(max_files))]]


_LOG_TS_RE = re.compile(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]")


def _log_line_sort_key(line: str) -> str:
    match = _LOG_TS_RE.match(line)
    return match.group(1) if match else ""
