from __future__ import annotations

import json
import os
import subprocess
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator

from db.sql import load_query


GPU_QUEUE_LOCK_BASE = 1964000


def detect_local_gpu_count() -> int:
    """Return the deterministic local GPU slot count without creating a CUDA context when possible."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "-L"],
            check=False,
            text=True,
            capture_output=True,
            timeout=2,
        )
        if result.returncode == 0:
            count = sum(1 for line in result.stdout.splitlines() if line.strip().startswith("GPU "))
            if count > 0:
                return count
    except Exception:
        pass

    try:
        import torch

        count = int(torch.cuda.device_count() or 0)
        if count > 0:
            return count
    except Exception:
        pass

    return 1


def resolve_local_gpu_slots(config: Any, *, detected_gpus: int | None = None) -> int:
    configured = str(config.get("LOCAL_GPU_QUEUE_SLOTS", "auto") or "auto").strip().lower()
    if configured not in {"", "auto", "detected"}:
        try:
            return max(1, int(configured))
        except ValueError:
            pass
    return max(1, int(detected_gpus or detect_local_gpu_count()))


@dataclass(frozen=True)
class LocalGpuLease:
    task_id: str
    task_type: str
    priority: int
    slot_index: int
    wait_seconds: float


class LocalGpuWorkCoordinator:
    """Cross-process coordinator for local GPU-backed work.

    The table records queue/audit state. PostgreSQL advisory locks provide the actual
    process-safe slot ownership and are released automatically if a process dies.
    """

    def __init__(
        self,
        *,
        database,
        logger=None,
        slot_count: int | None = None,
        detected_gpu_count: int | None = None,
        queue_timeout_seconds: float = 300,
        stale_running_after_seconds: int = 7200,
        poll_seconds: float = 0.1,
    ):
        self.database = database
        self.logger = logger
        self.detected_gpu_count = max(1, int(detected_gpu_count or slot_count or 1))
        self.slot_count = max(1, int(slot_count or 1))
        self.queue_timeout_seconds = max(1.0, float(queue_timeout_seconds or 300))
        self.stale_running_after_seconds = max(60, int(stale_running_after_seconds or 7200))
        self.poll_seconds = max(0.02, float(poll_seconds or 0.1))
        self.process_id = os.getpid()
        self._cleaned_abandoned = False

    def configure(self, *, slot_count: int | None = None, queue_timeout_seconds: float | None = None) -> None:
        if slot_count is not None:
            self.slot_count = max(1, int(slot_count or 1))
        if queue_timeout_seconds is not None:
            self.queue_timeout_seconds = max(1.0, float(queue_timeout_seconds or 300))

    @contextmanager
    def lease(
        self,
        *,
        task_type: str,
        priority: int,
        owner: str | None = None,
        details: dict[str, Any] | None = None,
        timeout_seconds: float | None = None,
    ) -> Iterator[LocalGpuLease]:
        task_id = str(uuid.uuid4())
        priority = int(priority)
        timeout = self.queue_timeout_seconds if timeout_seconds is None else max(1.0, float(timeout_seconds))
        self.cleanup_abandoned_once()
        self._insert_task(task_id, task_type, priority, owner, details or {})

        conn = None
        lock_key = None
        lease: LocalGpuLease | None = None
        try:
            conn, slot_index, wait_seconds = self._wait_for_slot(task_id, timeout)
            lock_key = self._lock_key(slot_index)
            lease = LocalGpuLease(
                task_id=task_id,
                task_type=task_type,
                priority=priority,
                slot_index=slot_index,
                wait_seconds=wait_seconds,
            )
            if wait_seconds > 0.25 and self.logger:
                self.logger.info(
                    f"⏳ Local GPU work waited {wait_seconds:.2f}s: {task_type} "
                    f"(priority {priority}, slot {slot_index + 1}/{self.slot_count})."
                )
            yield lease
            self._finish_task(conn, task_id, "completed", None)
        except TimeoutError as exc:
            self._finish_without_lease(task_id, "timed_out", str(exc))
            raise
        except Exception as exc:
            if conn is not None:
                self._finish_task(conn, task_id, "failed", str(exc))
            else:
                self._finish_without_lease(task_id, "failed", str(exc))
            raise
        finally:
            if conn is not None:
                if lock_key is not None:
                    try:
                        conn.execute(load_query("local_gpu_advisory_unlock.sql"), (lock_key,))
                        conn.commit()
                    except Exception:
                        conn.rollback()
                self.database._connection_pool().putconn(conn)

    def status(self, *, recent_limit: int = 10, window_seconds: int = 3600) -> dict[str, Any]:
        window = f"{max(60, int(window_seconds))} seconds"
        try:
            with self.database.connection() as conn:
                count_rows = conn.execute(load_query("local_gpu_work_counts.sql"), (window,)).fetchall()
                recent_rows = conn.execute(
                    load_query("local_gpu_work_recent.sql"),
                    (window, max(1, int(recent_limit))),
                ).fetchall()
        except Exception as exc:
            return {
                "enabled": False,
                "error": str(exc),
                "slots": self.slot_count,
                "detectedGpus": self.detected_gpu_count,
            }
        counts = {row["status"]: int(row["count"] or 0) for row in count_rows}
        return {
            "enabled": True,
            "slots": self.slot_count,
            "detectedGpus": self.detected_gpu_count,
            "processId": self.process_id,
            "queueTimeoutSeconds": self.queue_timeout_seconds,
            "active": counts.get("running", 0),
            "queued": counts.get("queued", 0),
            "completed": counts.get("completed", 0),
            "failed": counts.get("failed", 0),
            "timedOut": counts.get("timed_out", 0),
            "recent": [self._row_to_payload(row) for row in recent_rows],
        }

    def cleanup_abandoned_once(self) -> None:
        if self._cleaned_abandoned:
            return
        self._cleaned_abandoned = True
        try:
            with self.database.connection() as conn:
                conn.execute(
                    load_query("local_gpu_work_cleanup_abandoned.sql"),
                    (f"{self.stale_running_after_seconds} seconds",),
                )
        except Exception as exc:
            if self.logger:
                self.logger.warning(f"⚠️ Local GPU queue abandoned-work cleanup failed: {exc}")

    def _insert_task(
        self,
        task_id: str,
        task_type: str,
        priority: int,
        owner: str | None,
        details: dict[str, Any],
    ) -> None:
        with self.database.connection() as conn:
            conn.execute(
                load_query("local_gpu_work_insert.sql"),
                (task_id, task_type, priority, owner, self.process_id, json.dumps(details)),
            )

    def _wait_for_slot(self, task_id: str, timeout_seconds: float):
        started = time.monotonic()
        while True:
            elapsed = time.monotonic() - started
            if elapsed >= timeout_seconds:
                raise TimeoutError(f"Local GPU queue timed out after {timeout_seconds:.0f}s.")

            if not self._task_is_eligible(task_id):
                time.sleep(self.poll_seconds)
                continue

            for slot_index in range(self.slot_count):
                conn = self.database._connection_pool().getconn()
                lock_key = self._lock_key(slot_index)
                try:
                    row = conn.execute(load_query("local_gpu_advisory_try_lock.sql"), (lock_key,)).fetchone()
                    if not row or not row.get("acquired"):
                        conn.rollback()
                        self.database._connection_pool().putconn(conn)
                        continue
                    running_row = conn.execute(
                        load_query("local_gpu_work_mark_running.sql"),
                        (
                            slot_index,
                            self.process_id,
                            json.dumps({"slotCount": self.slot_count}),
                            task_id,
                        ),
                    ).fetchone()
                    conn.commit()
                    wait_seconds = float((running_row or {}).get("wait_seconds") or 0.0)
                    return conn, slot_index, wait_seconds
                except Exception:
                    conn.rollback()
                    try:
                        conn.execute(load_query("local_gpu_advisory_unlock.sql"), (lock_key,))
                        conn.commit()
                    except Exception:
                        conn.rollback()
                    self.database._connection_pool().putconn(conn)
                    raise

            time.sleep(self.poll_seconds)

    def _task_is_eligible(self, task_id: str) -> bool:
        with self.database.connection() as conn:
            row = conn.execute(load_query("local_gpu_work_eligible.sql"), (task_id,)).fetchone()
        return bool(row and row.get("eligible"))

    def _finish_task(self, conn, task_id: str, status: str, error_message: str | None) -> None:
        conn.execute(load_query("local_gpu_work_finish.sql"), (status, error_message, task_id))
        conn.commit()

    def _finish_without_lease(self, task_id: str, status: str, error_message: str | None) -> None:
        try:
            with self.database.connection() as conn:
                conn.execute(load_query("local_gpu_work_finish.sql"), (status, error_message, task_id))
        except Exception:
            if self.logger:
                self.logger.warning(f"⚠️ Could not mark local GPU work {task_id} as {status}.")

    @staticmethod
    def _lock_key(slot_index: int) -> int:
        return GPU_QUEUE_LOCK_BASE + int(slot_index)

    @staticmethod
    def _row_to_payload(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "taskId": row.get("task_id"),
            "taskType": row.get("task_type"),
            "priority": row.get("priority"),
            "owner": row.get("owner"),
            "processId": row.get("process_id"),
            "slotIndex": row.get("slot_index"),
            "status": row.get("status"),
            "waitSeconds": float(row["wait_seconds"]) if row.get("wait_seconds") is not None else None,
            "durationSeconds": float(row["duration_seconds"]) if row.get("duration_seconds") is not None else None,
            "error": row.get("error_message"),
            "details": row.get("details") or {},
            "createdAt": row.get("created_at"),
            "startedAt": row.get("started_at"),
            "finishedAt": row.get("finished_at"),
            "updatedAt": row.get("updated_at"),
        }


class GpuQueuedEmbedder:
    def __init__(self, embedder, coordinator: LocalGpuWorkCoordinator, *, priority: int, owner: str):
        self.embedder = embedder
        self.coordinator = coordinator
        self.priority = int(priority)
        self.owner = owner

    @property
    def resident(self) -> bool:
        return bool(getattr(self.embedder, "resident", True))

    def encode(self, texts, *args, **kwargs):
        count = len(texts) if hasattr(texts, "__len__") else None
        with self.coordinator.lease(
            task_type="embedding",
            priority=self.priority,
            owner=self.owner,
            details={"items": count},
        ):
            return self.embedder.encode(texts, *args, **kwargs)

    def unload(self) -> bool:
        if hasattr(self.embedder, "unload"):
            return bool(self.embedder.unload())
        return False
