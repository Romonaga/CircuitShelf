from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class LogRetentionResult:
    removed: int
    failures: int
    checked: int
    retention_days: float


def cleanup_old_logs(
    configured_log_file: str | Path,
    active_log_file: str | Path | None,
    retention_days: int | float,
    now: float | None = None,
    logger=None,
) -> LogRetentionResult:
    retention_days = float(retention_days or 0)
    if retention_days <= 0:
        return LogRetentionResult(removed=0, failures=0, checked=0, retention_days=retention_days)

    configured_path = Path(configured_log_file)
    log_dir = configured_path.parent if configured_path.parent != Path("") else Path(".")
    if not log_dir.exists() or not log_dir.is_dir():
        return LogRetentionResult(removed=0, failures=0, checked=0, retention_days=retention_days)

    active_path = _resolved_path(active_log_file) if active_log_file else None
    cutoff = (time.time() if now is None else now) - (retention_days * 86400)
    removed = 0
    failures = 0
    checked = 0

    try:
        candidates = list(_candidate_logs(log_dir, configured_path.name))
    except OSError as exc:
        if logger:
            logger.warning(f"Could not inspect log directory for retention cleanup: {exc}")
        return LogRetentionResult(removed=0, failures=1, checked=0, retention_days=retention_days)

    for log_path in candidates:
        checked += 1
        try:
            if active_path and _resolved_path(log_path) == active_path:
                continue
            if not log_path.is_file():
                continue
            if log_path.stat().st_mtime >= cutoff:
                continue
            log_path.unlink()
            removed += 1
        except OSError as exc:
            failures += 1
            if logger:
                logger.debug(f"Could not remove old log file {log_path}: {exc}")

    if logger and (removed or failures):
        logger.info(
            f"Log retention cleaned {removed} old log file(s); "
            f"failures={failures}, retention_days={retention_days:g}."
        )

    return LogRetentionResult(
        removed=removed,
        failures=failures,
        checked=checked,
        retention_days=retention_days,
    )


def _candidate_logs(log_dir: Path, configured_name: str) -> Iterable[Path]:
    configured = Path(configured_name)
    stem = configured.stem
    suffix = configured.suffix

    for path in log_dir.iterdir():
        name = path.name
        if name == configured_name:
            yield path
        elif name.startswith(f"{configured_name}."):
            yield path
        elif suffix and name.startswith(f"{stem}_") and name.endswith(suffix):
            yield path


def _resolved_path(path: str | Path) -> Path:
    return Path(path).expanduser().resolve(strict=False)
