from __future__ import annotations

import os
import re
import time
from pathlib import Path


LOCK_PREFIX = ".circuitshelf-upload-"
LOCK_SUFFIX = ".lock"
DEFAULT_STALE_SECONDS = 30 * 60


def normalize_upload_session_id(session_id: str | None) -> str:
    value = str(session_id or "").strip()
    if not value:
        return ""
    safe = re.sub(r"[^A-Za-z0-9_.-]", "-", value)
    return safe[:96]


def upload_session_lock_path(training_dir: str, session_id: str) -> str:
    safe_id = normalize_upload_session_id(session_id)
    if not safe_id:
        raise ValueError("Upload session id is required.")
    return os.path.join(training_dir, f"{LOCK_PREFIX}{safe_id}{LOCK_SUFFIX}")


def mark_upload_session_active(training_dir: str, session_id: str | None) -> str:
    safe_id = normalize_upload_session_id(session_id)
    if not safe_id:
        return ""
    os.makedirs(training_dir, exist_ok=True)
    lock_path = upload_session_lock_path(training_dir, safe_id)
    with open(lock_path, "w", encoding="utf-8") as handle:
        handle.write(str(time.time()))
    return safe_id


def complete_upload_session(training_dir: str, session_id: str | None) -> None:
    safe_id = normalize_upload_session_id(session_id)
    if not safe_id:
        return
    lock_path = upload_session_lock_path(training_dir, safe_id)
    try:
        os.remove(lock_path)
    except FileNotFoundError:
        return


def active_upload_sessions(training_dir: str, *, stale_seconds: int = DEFAULT_STALE_SECONDS) -> list[str]:
    root = Path(training_dir)
    if not root.exists():
        return []

    now = time.time()
    active: list[str] = []
    for path in root.glob(f"{LOCK_PREFIX}*{LOCK_SUFFIX}"):
        try:
            age = now - path.stat().st_mtime
        except FileNotFoundError:
            continue
        if age > stale_seconds:
            try:
                path.unlink()
            except FileNotFoundError:
                pass
            continue
        name = path.name[len(LOCK_PREFIX):-len(LOCK_SUFFIX)]
        if name:
            active.append(name)
    return sorted(active)
