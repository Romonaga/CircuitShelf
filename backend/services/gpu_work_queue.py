from __future__ import annotations

import json
import os
import subprocess
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator

from backend.domain.statuses import LocalGpuWorkStatusId, local_gpu_work_status_code
from db.sql import load_query


GPU_QUEUE_LOCK_BASE = 1964000
GPU_QUEUE_LOCK_OFFSETS = {
    "local_llm": 0,
    "cuda_batch": 1000,
    "ocr_cuda": 2000,
}
GPU_QUEUE_ADMISSION_LOCK_BASE = GPU_QUEUE_LOCK_BASE + 900000


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


def _resolve_slot_count(
    config: Any,
    key: str,
    *,
    detected_gpus: int | None = None,
    auto_multiplier: int = 1,
    auto_max: int | None = None,
) -> int:
    configured = str(config.get(key, "auto") or "auto").strip().lower()
    if configured not in {"", "auto", "detected"}:
        try:
            return max(1, int(configured))
        except ValueError:
            pass
    detected = max(1, int(detected_gpus or detect_local_gpu_count()))
    slots = max(1, detected * max(1, int(auto_multiplier or 1)))
    if auto_max is not None:
        slots = min(slots, max(1, int(auto_max)))
    return slots


def resolve_local_gpu_llm_slots(config: Any, *, detected_gpus: int | None = None) -> int:
    return _resolve_slot_count(config, "LOCAL_GPU_LLM_SLOTS", detected_gpus=detected_gpus)


def resolve_local_gpu_cuda_slots(config: Any, *, detected_gpus: int | None = None) -> int:
    return _resolve_slot_count(
        config,
        "LOCAL_GPU_CUDA_SLOTS",
        detected_gpus=detected_gpus,
        auto_multiplier=2,
        auto_max=4,
    )


def resolve_local_gpu_ocr_slots(config: Any, *, detected_gpus: int | None = None) -> int:
    return _resolve_slot_count(
        config,
        "LOCAL_GPU_OCR_SLOTS",
        detected_gpus=detected_gpus,
        auto_multiplier=2,
        auto_max=4,
    )


@dataclass(frozen=True)
class LocalGpuLease:
    task_id: str
    resource_class: str
    task_type: str
    priority: int
    slot_index: int
    slot_count: int
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
        llm_slot_count: int | None = None,
        cuda_slot_count: int | None = None,
        ocr_slot_count: int | None = None,
        detected_gpu_count: int | None = None,
        queue_timeout_seconds: float = 300,
        stale_running_after_seconds: int = 900,
        stale_queued_after_seconds: int | None = None,
        poll_seconds: float = 0.1,
        cleanup_interval_seconds: float = 30,
        heartbeat_interval_seconds: float = 15,
    ):
        self.database = database
        self.logger = logger
        fallback_slots = max(1, int(slot_count or 1))
        self.detected_gpu_count = max(1, int(detected_gpu_count or fallback_slots or 1))
        self.llm_slot_count = max(1, int(llm_slot_count or fallback_slots))
        self.cuda_slot_count = max(1, int(cuda_slot_count or fallback_slots))
        self.ocr_slot_count = max(1, int(ocr_slot_count or self.cuda_slot_count))
        self.queue_timeout_seconds = max(1.0, float(queue_timeout_seconds or 300))
        self.stale_running_after_seconds = max(60, int(stale_running_after_seconds or 7200))
        self.stale_queued_after_seconds = max(
            60,
            int(stale_queued_after_seconds or max(600, self.queue_timeout_seconds * 2)),
        )
        self.poll_seconds = max(0.02, float(poll_seconds or 0.1))
        self.cleanup_interval_seconds = max(5.0, float(cleanup_interval_seconds or 30))
        self.heartbeat_interval_seconds = max(5.0, float(heartbeat_interval_seconds or 15))
        self.process_id = os.getpid()
        self._cleaned_abandoned = False
        self._last_cleanup_at = 0.0

    @property
    def slot_count(self) -> int:
        return self.llm_slot_count

    def configure(
        self,
        *,
        slot_count: int | None = None,
        llm_slot_count: int | None = None,
        cuda_slot_count: int | None = None,
        ocr_slot_count: int | None = None,
        queue_timeout_seconds: float | None = None,
    ) -> None:
        if slot_count is not None:
            self.llm_slot_count = max(1, int(slot_count or 1))
        if llm_slot_count is not None:
            self.llm_slot_count = max(1, int(llm_slot_count or 1))
        if cuda_slot_count is not None:
            self.cuda_slot_count = max(1, int(cuda_slot_count or 1))
        if ocr_slot_count is not None:
            self.ocr_slot_count = max(1, int(ocr_slot_count or 1))
        if queue_timeout_seconds is not None:
            self.queue_timeout_seconds = max(1.0, float(queue_timeout_seconds or 300))

    @contextmanager
    def lease(
        self,
        *,
        task_type: str,
        priority: int,
        resource_class: str | None = None,
        owner: str | None = None,
        details: dict[str, Any] | None = None,
        timeout_seconds: float | None = None,
        admission_max_pending: int | None = None,
        admission_timeout_seconds: float | None = None,
    ) -> Iterator[LocalGpuLease]:
        task_id = str(uuid.uuid4())
        priority = int(priority)
        resource_class = self._normalize_resource_class(resource_class or self._default_resource_class(task_type))
        timeout = self.queue_timeout_seconds if timeout_seconds is None else max(1.0, float(timeout_seconds))
        self.cleanup_abandoned()
        admission_wait_seconds = self._admit_task(
            task_id=task_id,
            resource_class=resource_class,
            task_type=task_type,
            priority=priority,
            owner=owner,
            details=details or {},
            admission_max_pending=admission_max_pending,
            admission_timeout_seconds=admission_timeout_seconds,
        )
        if admission_wait_seconds > 0.25 and self.logger:
            self.logger.info(
                f"⏳ Local GPU {resource_class} admission waited {admission_wait_seconds:.2f}s: {task_type} "
                f"(max pending {admission_max_pending})."
            )

        conn = None
        lock_key = None
        lease: LocalGpuLease | None = None
        run_started: float | None = None
        heartbeat_stop: threading.Event | None = None
        heartbeat_thread: threading.Thread | None = None
        try:
            conn, slot_index, wait_seconds = self._wait_for_slot(task_id, resource_class, timeout)
            slot_count = self._slot_count_for(resource_class)
            lock_key = self._lock_key(resource_class, slot_index)
            lease = LocalGpuLease(
                task_id=task_id,
                resource_class=resource_class,
                task_type=task_type,
                priority=priority,
                slot_index=slot_index,
                slot_count=slot_count,
                wait_seconds=wait_seconds,
            )
            if wait_seconds > 0.25 and self.logger:
                self.logger.info(
                    f"⏳ Local GPU {resource_class} work waited {wait_seconds:.2f}s: {task_type} "
                    f"(priority {priority}, slot {slot_index + 1}/{slot_count})."
                )
            run_started = time.monotonic()
            if self.logger:
                self.logger.info(
                    f"🎮 Local GPU work start: "
                    f"{self._log_context(lease, owner=owner, details=details or {})}."
                )
            heartbeat_stop, heartbeat_thread = self._start_heartbeat(task_id)
            yield lease
            if self.logger:
                self.logger.info(
                    f"✅ Local GPU work complete: "
                    f"{self._log_context(lease, owner=owner, details=details or {}, duration=time.monotonic() - run_started)}."
                )
            self._finish_task(conn, task_id, LocalGpuWorkStatusId.COMPLETED, None)
        except TimeoutError as exc:
            self._finish_without_lease(task_id, LocalGpuWorkStatusId.TIMED_OUT, str(exc))
            raise
        except Exception as exc:
            if lease is not None and self.logger:
                duration = (time.monotonic() - run_started) if run_started is not None else None
                self.logger.warning(
                    f"❌ Local GPU work failed: "
                    f"{self._log_context(lease, owner=owner, details=details or {}, duration=duration)}; "
                    f"{exc}"
                )
            if conn is not None:
                self._finish_task(conn, task_id, LocalGpuWorkStatusId.FAILED, str(exc))
            else:
                self._finish_without_lease(task_id, LocalGpuWorkStatusId.FAILED, str(exc))
            raise
        finally:
            self._stop_heartbeat(heartbeat_stop, heartbeat_thread)
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
            self.cleanup_abandoned()
            with self.database.connection() as conn:
                count_rows = conn.execute(load_query("local_gpu_work_counts.sql"), (window,)).fetchall()
                live_count_rows = conn.execute(load_query("local_gpu_work_live_by_resource_counts.sql")).fetchall()
                recent_rows = conn.execute(
                    load_query("local_gpu_work_recent.sql"),
                    (window, max(1, int(recent_limit))),
                ).fetchall()
        except Exception as exc:
            return {
                "enabled": False,
                "error": str(exc),
                "slots": self.llm_slot_count,
                "llmSlots": self.llm_slot_count,
                "cudaSlots": self.cuda_slot_count,
                "ocrSlots": self.ocr_slot_count,
                "detectedGpus": self.detected_gpu_count,
            }
        counts: dict[str, int] = {}
        counts_by_resource: dict[str, dict[str, int]] = {}
        for row in count_rows:
            status = str(row["status"])
            resource = str(row.get("resource_class") or "unknown")
            count = int(row["count"] or 0)
            if status in {"queued", "running"}:
                continue
            counts[status] = counts.get(status, 0) + count
            counts_by_resource.setdefault(resource, {})[status] = count
        for row in live_count_rows:
            status = str(row["status"])
            resource = str(row.get("resource_class") or "unknown")
            count = int(row["count"] or 0)
            counts[status] = counts.get(status, 0) + count
            counts_by_resource.setdefault(resource, {})[status] = count
        return {
            "enabled": True,
            "slots": self.llm_slot_count,
            "llmSlots": self.llm_slot_count,
            "cudaSlots": self.cuda_slot_count,
            "ocrSlots": self.ocr_slot_count,
            "detectedGpus": self.detected_gpu_count,
            "processId": self.process_id,
            "queueTimeoutSeconds": self.queue_timeout_seconds,
            "active": counts.get("running", 0),
            "queued": counts.get("queued", 0),
            "completed": counts.get("completed", 0),
            "failed": counts.get("failed", 0),
            "timedOut": counts.get("timed_out", 0),
            "byResource": counts_by_resource,
            "recent": [self._row_to_payload(row) for row in recent_rows],
        }

    def live_pressure(self, resource_class: str | None = None) -> dict[str, Any]:
        resource_class = self._normalize_resource_class(resource_class or "local_llm")
        try:
            self.cleanup_abandoned()
            with self.database.connection() as conn:
                rows = conn.execute(load_query("local_gpu_work_live_counts.sql"), (resource_class,)).fetchall()
        except Exception as exc:
            return {
                "enabled": False,
                "resourceClass": resource_class,
                "error": str(exc),
                "slots": self._slot_count_for(resource_class),
                "queued": 0,
                "running": 0,
                "pending": 0,
            }
        counts = {str(row["status"]): int(row["count"] or 0) for row in rows}
        queued = counts.get("queued", 0)
        running = counts.get("running", 0)
        return {
            "enabled": True,
            "resourceClass": resource_class,
            "slots": self._slot_count_for(resource_class),
            "queued": queued,
            "running": running,
            "pending": queued + running,
        }

    def cleanup_abandoned_once(self) -> None:
        if self._cleaned_abandoned:
            return
        self._cleaned_abandoned = True
        self.cleanup_abandoned(force=True)

    def cleanup_abandoned(self, *, force: bool = False) -> None:
        now = time.monotonic()
        if not force and (now - self._last_cleanup_at) < self.cleanup_interval_seconds:
            return
        self._last_cleanup_at = now
        try:
            with self.database.connection() as conn:
                conn.execute(
                    load_query("local_gpu_work_cleanup_abandoned.sql"),
                    (
                        f"{self.stale_running_after_seconds} seconds",
                        f"{self.stale_queued_after_seconds} seconds",
                    ),
                )
        except Exception as exc:
            if self.logger:
                self.logger.warning(f"⚠️ Local GPU queue abandoned-work cleanup failed: {exc}")

    def _start_heartbeat(self, task_id: str) -> tuple[threading.Event, threading.Thread]:
        stop_event = threading.Event()

        def heartbeat() -> None:
            while not stop_event.wait(self.heartbeat_interval_seconds):
                try:
                    with self.database.connection() as heartbeat_conn:
                        heartbeat_conn.execute(load_query("local_gpu_work_touch.sql"), (task_id,))
                except Exception as exc:
                    if self.logger:
                        self.logger.warning(f"⚠️ Local GPU work heartbeat failed for {task_id}: {exc}")
                    return

        thread = threading.Thread(
            target=heartbeat,
            name=f"local-gpu-heartbeat-{task_id[:8]}",
            daemon=True,
        )
        thread.start()
        return stop_event, thread

    @staticmethod
    def _stop_heartbeat(stop_event: threading.Event | None, thread: threading.Thread | None) -> None:
        if stop_event is None or thread is None:
            return
        stop_event.set()
        thread.join(timeout=1)

    def _insert_task(
        self,
        task_id: str,
        resource_class: str,
        task_type: str,
        priority: int,
        owner: str | None,
        details: dict[str, Any],
    ) -> None:
        with self.database.connection() as conn:
            self._insert_task_on_conn(conn, task_id, resource_class, task_type, priority, owner, details)

    def _insert_task_on_conn(
        self,
        conn,
        task_id: str,
        resource_class: str,
        task_type: str,
        priority: int,
        owner: str | None,
        details: dict[str, Any],
    ) -> None:
        conn.execute(
            load_query("local_gpu_work_insert.sql"),
            (task_id, resource_class, task_type, priority, owner, self.process_id, json.dumps(details)),
        )

    def _admit_task(
        self,
        *,
        task_id: str,
        resource_class: str,
        task_type: str,
        priority: int,
        owner: str | None,
        details: dict[str, Any],
        admission_max_pending: int | None,
        admission_timeout_seconds: float | None,
    ) -> float:
        if admission_max_pending is None:
            self._insert_task(task_id, resource_class, task_type, priority, owner, details)
            return 0.0

        max_pending = max(1, int(admission_max_pending))
        timeout = self.queue_timeout_seconds if admission_timeout_seconds is None else max(
            1.0,
            float(admission_timeout_seconds),
        )
        started = time.monotonic()
        lock_key = self._admission_lock_key(resource_class)
        while True:
            elapsed = time.monotonic() - started
            if elapsed >= timeout:
                raise TimeoutError(
                    f"Local GPU {resource_class} admission timed out after {timeout:.0f}s "
                    f"waiting for pending work below {max_pending}."
                )

            conn = self.database._connection_pool().getconn()
            lock_acquired = False
            try:
                lock_row = conn.execute(load_query("local_gpu_advisory_try_lock.sql"), (lock_key,)).fetchone()
                lock_acquired = bool(lock_row and lock_row.get("acquired"))
                if not lock_acquired:
                    conn.rollback()
                else:
                    rows = conn.execute(load_query("local_gpu_work_live_counts.sql"), (resource_class,)).fetchall()
                    pending = sum(int(row["count"] or 0) for row in rows)
                    if pending < max_pending:
                        self._insert_task_on_conn(conn, task_id, resource_class, task_type, priority, owner, details)
                        conn.commit()
                        return elapsed

                    conn.rollback()
            except Exception:
                conn.rollback()
                raise
            finally:
                if lock_acquired:
                    try:
                        conn.execute(load_query("local_gpu_advisory_unlock.sql"), (lock_key,))
                        conn.commit()
                    except Exception:
                        conn.rollback()
                self.database._connection_pool().putconn(conn)

            time.sleep(self.poll_seconds)

    def _wait_for_slot(self, task_id: str, resource_class: str, timeout_seconds: float):
        started = time.monotonic()
        slot_count = self._slot_count_for(resource_class)
        while True:
            elapsed = time.monotonic() - started
            if elapsed >= timeout_seconds:
                raise TimeoutError(f"Local GPU queue timed out after {timeout_seconds:.0f}s.")

            if not self._task_is_eligible(task_id):
                time.sleep(self.poll_seconds)
                continue

            for slot_index in range(slot_count):
                conn = self.database._connection_pool().getconn()
                lock_key = self._lock_key(resource_class, slot_index)
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
                            json.dumps({"slotCount": slot_count, "resourceClass": resource_class}),
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

    def _finish_task(self, conn, task_id: str, status: LocalGpuWorkStatusId, error_message: str | None) -> None:
        conn.execute(load_query("local_gpu_work_finish.sql"), (int(status), error_message, task_id))
        conn.commit()

    def _finish_without_lease(self, task_id: str, status: LocalGpuWorkStatusId, error_message: str | None) -> None:
        try:
            with self.database.connection() as conn:
                conn.execute(load_query("local_gpu_work_finish.sql"), (int(status), error_message, task_id))
        except Exception:
            if self.logger:
                self.logger.warning(f"⚠️ Could not mark local GPU work {task_id} as {local_gpu_work_status_code(status)}.")

    @staticmethod
    def _default_resource_class(task_type: str) -> str:
        normalized = str(task_type or "").lower()
        if normalized == "paddleocr":
            return "ocr_cuda"
        if normalized in {"embedding", "rerank"}:
            return "cuda_batch"
        return "local_llm"

    @staticmethod
    def _normalize_resource_class(resource_class: str) -> str:
        value = str(resource_class or "local_llm").strip().lower()
        return value if value in GPU_QUEUE_LOCK_OFFSETS else "local_llm"

    def _slot_count_for(self, resource_class: str) -> int:
        if resource_class == "cuda_batch":
            return self.cuda_slot_count
        if resource_class == "ocr_cuda":
            return self.ocr_slot_count
        return self.llm_slot_count

    @staticmethod
    def _lock_key(resource_class: str, slot_index: int) -> int:
        offset = GPU_QUEUE_LOCK_OFFSETS.get(resource_class, 0)
        return GPU_QUEUE_LOCK_BASE + offset + int(slot_index)

    @staticmethod
    def _admission_lock_key(resource_class: str) -> int:
        offset = GPU_QUEUE_LOCK_OFFSETS.get(resource_class, 0)
        return GPU_QUEUE_ADMISSION_LOCK_BASE + offset

    @staticmethod
    def _format_details(details: dict[str, Any], max_items: int = 5) -> str:
        parts: list[str] = []
        for index, (key, value) in enumerate(details.items()):
            if index >= max_items:
                parts.append(f"+{len(details) - max_items} more")
                break
            if value is None:
                continue
            if isinstance(value, float):
                rendered = f"{value:.3g}"
            else:
                rendered = str(value)
            if len(rendered) > 80:
                rendered = f"{rendered[:77]}..."
            parts.append(f"{key}={rendered}")
        return ", ".join(parts)

    @classmethod
    def _log_context(
        cls,
        lease: LocalGpuLease,
        *,
        owner: str | None,
        details: dict[str, Any],
        duration: float | None = None,
    ) -> str:
        context = [
            f"{lease.task_type} via {lease.resource_class}",
            f"owner={owner or 'n/a'}",
            f"priority={lease.priority}",
            f"slot={lease.slot_index + 1}/{lease.slot_count}",
            f"wait={lease.wait_seconds:.2f}s",
        ]
        if duration is not None:
            context.append(f"duration={duration:.2f}s")
        detail_text = cls._format_details(details)
        if detail_text:
            context.append(detail_text)
        return " | ".join(context)

    @staticmethod
    def _row_to_payload(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "taskId": row.get("task_id"),
            "resourceClass": row.get("resource_class"),
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
            resource_class="cuda_batch",
            priority=self.priority,
            owner=self.owner,
            details={"items": count},
        ):
            return self.embedder.encode(texts, *args, **kwargs)

    def unload(self) -> bool:
        if hasattr(self.embedder, "unload"):
            return bool(self.embedder.unload())
        return False
