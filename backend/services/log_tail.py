from __future__ import annotations

import os
from dataclasses import dataclass


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
