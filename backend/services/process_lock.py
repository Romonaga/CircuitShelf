from __future__ import annotations

import json
import os
import signal
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows fallback path
    fcntl = None


class ProcessLockError(RuntimeError):
    pass


def process_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def read_pid_file(path: str | os.PathLike[str]) -> dict[str, Any] | None:
    pid_path = Path(path)
    if not pid_path.exists():
        return None
    try:
        raw = pid_path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        try:
            return {"pid": int(raw)}
        except ValueError:
            return None
    return data if isinstance(data, dict) else None


def pid_file_process(path: str | os.PathLike[str]) -> int | None:
    data = read_pid_file(path)
    if not data:
        return None
    try:
        return int(data.get("pid") or 0)
    except (TypeError, ValueError):
        return None


def terminate_pid_file_process(path: str | os.PathLike[str], *, timeout_seconds: float = 20.0) -> bool:
    pid = pid_file_process(path)
    pid_path = Path(path)
    if not pid:
        if pid_path.exists():
            pid_path.unlink(missing_ok=True)
        return False
    if not process_exists(pid):
        pid_path.unlink(missing_ok=True)
        return False

    os.kill(pid, signal.SIGTERM)
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if not process_exists(pid):
            pid_path.unlink(missing_ok=True)
            return True
        time.sleep(0.2)

    if process_exists(pid):
        force_signal = getattr(signal, "SIGKILL", signal.SIGTERM)
        os.kill(pid, force_signal)
    pid_path.unlink(missing_ok=True)
    return True


@dataclass
class ProcessLock:
    path: Path
    name: str = "CircuitShelf"
    _handle: Any = None

    def acquire(self) -> "ProcessLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("a+", encoding="utf-8")
        if fcntl is not None:
            try:
                fcntl.flock(self._handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                pid = pid_file_process(self.path)
                label = f" PID {pid}" if pid else ""
                self._handle.close()
                self._handle = None
                raise ProcessLockError(f"{self.name} is already running{label}.") from exc
        else:
            pid = pid_file_process(self.path)
            if pid and process_exists(pid):
                self._handle.close()
                self._handle = None
                raise ProcessLockError(f"{self.name} is already running PID {pid}.")

        self._handle.seek(0)
        self._handle.truncate()
        self._handle.write(
            json.dumps(
                {
                    "pid": os.getpid(),
                    "name": self.name,
                    "startedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                },
                indent=2,
            )
        )
        self._handle.write("\n")
        self._handle.flush()
        os.fsync(self._handle.fileno())
        return self

    def release(self) -> None:
        if not self._handle:
            return
        try:
            if fcntl is not None:
                fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        finally:
            self._handle.close()
            self._handle = None
            self.path.unlink(missing_ok=True)

    def __enter__(self) -> "ProcessLock":
        return self.acquire()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()


def acquire_process_lock(path: str | os.PathLike[str], *, name: str = "CircuitShelf") -> ProcessLock:
    return ProcessLock(Path(path), name=name)
