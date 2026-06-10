from __future__ import annotations

import json
import math
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


def _query_nvidia_smi_gpu_lines(query: str) -> list[list[str]]:
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                f"--query-gpu={query}",
                "--format=csv,noheader,nounits",
            ],
            check=False,
            text=True,
            capture_output=True,
            timeout=2,
        )
    except Exception:
        return []
    if result.returncode != 0:
        return []
    rows: list[list[str]] = []
    for line in result.stdout.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if any(parts):
            rows.append(parts)
    return rows


def detect_local_gpu_count() -> int:
    """Return the local GPU count without creating a CUDA context when possible."""
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


def detect_local_gpu_memory_total_mib() -> int | None:
    """Return the smallest detected GPU VRAM size in MiB.

    Multi-GPU hosts are sized from the least capable card so auto settings do not
    overcommit a mixed installation.
    """
    totals: list[int] = []
    for row in _query_nvidia_smi_gpu_lines("memory.total"):
        if not row:
            continue
        try:
            totals.append(int(float(row[0])))
        except (TypeError, ValueError):
            continue
    if totals:
        return max(1, min(totals))

    try:
        import torch

        if torch.cuda.is_available():
            for index in range(torch.cuda.device_count()):
                props = torch.cuda.get_device_properties(index)
                totals.append(int(props.total_memory / (1024 * 1024)))
    except Exception:
        pass
    return max(1, min(totals)) if totals else None


def read_local_gpu_pressure() -> dict[str, Any]:
    """Return a small, cheap pressure sample for queue admission decisions."""
    rows = _query_nvidia_smi_gpu_lines("utilization.gpu,memory.used,memory.total,temperature.gpu")
    samples: list[dict[str, float]] = []
    for row in rows:
        if len(row) < 4:
            continue
        try:
            gpu_percent = float(row[0])
            memory_used = float(row[1])
            memory_total = float(row[2])
            temperature_c = float(row[3])
        except (TypeError, ValueError):
            continue
        samples.append(
            {
                "gpuPercent": gpu_percent,
                "memoryUsedMiB": memory_used,
                "memoryTotalMiB": memory_total,
                "memoryUsedPercent": round((memory_used / memory_total) * 100.0, 2) if memory_total else 0.0,
                "temperatureC": temperature_c,
            }
        )
    if not samples:
        return {"available": False}
    return {
        "available": True,
        "gpuPercent": max(sample["gpuPercent"] for sample in samples),
        "memoryUsedPercent": max(sample["memoryUsedPercent"] for sample in samples),
        "memoryUsedMiB": max(sample["memoryUsedMiB"] for sample in samples),
        "memoryTotalMiB": min(sample["memoryTotalMiB"] for sample in samples),
        "temperatureC": max(sample["temperatureC"] for sample in samples),
    }


def _optional_float(value: Any) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def resolve_adaptive_ocr_slots(
    max_slots: int,
    pressure: dict[str, Any],
    *,
    running_slots: int = 0,
) -> dict[str, Any]:
    """Choose currently admitted OCR lanes from live GPU pressure.

    The target is the number of new OCR lanes we are willing to admit right now.
    The reported active slot count is never allowed below already-running work,
    because running OCR jobs cannot be revoked and displaying 4/3 is misleading.
    """
    max_slots = max(1, int(max_slots or 1))
    running_slots = max(0, min(max_slots, int(running_slots or 0)))
    if not pressure.get("available"):
        return {
            "enabled": False,
            "activeSlots": max_slots,
            "targetSlots": max_slots,
            "maxSlots": max_slots,
            "runningSlots": running_slots,
            "reason": "gpu telemetry unavailable",
            "pressure": pressure,
        }

    gpu_percent = _optional_float(pressure.get("gpuPercent")) or 0.0
    vram_percent = _optional_float(pressure.get("memoryUsedPercent")) or 0.0
    temperature_c = _optional_float(pressure.get("temperatureC")) or 0.0
    if temperature_c >= 82 or vram_percent >= 94:
        ratio = 0.25
        reason = "thermal or VRAM guard"
        pressure_level = "hard"
    elif gpu_percent >= 92 or vram_percent >= 90:
        ratio = 0.50
        reason = "high GPU pressure"
        pressure_level = "high"
    elif gpu_percent >= 82 or vram_percent >= 88:
        ratio = 0.75
        reason = "moderate GPU pressure"
        pressure_level = "moderate"
    else:
        ratio = 1.0
        reason = "GPU headroom available"
        pressure_level = "headroom"

    target_slots = max(1, min(max_slots, math.ceil(max_slots * ratio)))
    active_slots = max(target_slots, running_slots)
    return {
        "enabled": True,
        "activeSlots": active_slots,
        "targetSlots": target_slots,
        "rawTargetSlots": target_slots,
        "maxSlots": max_slots,
        "runningSlots": running_slots,
        "reason": reason,
        "pressureLevel": pressure_level,
        "pressure": pressure,
    }


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


def resolve_local_gpu_ocr_slots(
    config: Any,
    *,
    detected_gpus: int | None = None,
    gpu_memory_total_mib: int | None = None,
) -> int:
    configured = str(config.get("LOCAL_GPU_OCR_SLOTS", "auto") or "auto").strip().lower()
    if configured not in {"", "auto", "detected"}:
        try:
            return max(1, int(configured))
        except ValueError:
            pass

    detected = max(1, int(detected_gpus or detect_local_gpu_count()))
    total_mib = gpu_memory_total_mib or detect_local_gpu_memory_total_mib()
    if not total_mib:
        lanes_per_gpu = 1
    else:
        total_gib = float(total_mib) / 1024.0
        if total_gib >= 40:
            lanes_per_gpu = 10
        elif total_gib >= 20:
            lanes_per_gpu = 8
        elif total_gib >= 12:
            lanes_per_gpu = 4
        else:
            lanes_per_gpu = 1

    return max(1, min(detected * lanes_per_gpu, detected * 10, 40))


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
        poll_seconds: float = 0.05,
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
        self.poll_seconds = max(0.02, float(poll_seconds or 0.05))
        self.cleanup_interval_seconds = max(5.0, float(cleanup_interval_seconds or 30))
        self.heartbeat_interval_seconds = max(5.0, float(heartbeat_interval_seconds or 15))
        self.process_id = os.getpid()
        self._cleaned_abandoned = False
        self._last_cleanup_at = 0.0
        self._pressure_lock = threading.Lock()
        self._pressure_sample: tuple[float, dict[str, Any]] | None = None
        self._ocr_adaptive_lock = threading.Lock()
        self._ocr_target_slots: int | None = None
        self._ocr_pressure_strikes = 0

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
            with self._ocr_adaptive_lock:
                self._ocr_target_slots = min(self._ocr_target_slots or self.ocr_slot_count, self.ocr_slot_count)
                self._ocr_pressure_strikes = 0
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
            conn, slot_index, wait_seconds, slot_count = self._wait_for_slot(task_id, resource_class, timeout)
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
                wait_rows = conn.execute(load_query("local_gpu_work_queue_wait_summary.sql"), (window,)).fetchall()
                recent_rows = conn.execute(
                    load_query("local_gpu_work_recent.sql"),
                    (window, max(1, int(recent_limit))),
                ).fetchall()
            running_by_resource = self._running_counts_by_resource(live_count_rows)
            adaptive_slots = self._adaptive_slots_payload(running_by_resource=running_by_resource)
        except Exception as exc:
            return {
                "enabled": False,
                "error": str(exc),
                "slots": self.llm_slot_count,
                "llmSlots": self.llm_slot_count,
                "cudaSlots": self.cuda_slot_count,
                "ocrSlots": self.ocr_slot_count,
                "adaptiveSlots": self._adaptive_slots_payload(),
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
        wait_summary = self._wait_summary_payload(wait_rows)
        for resource, summary in wait_summary.get("byResource", {}).items():
            counts_by_resource.setdefault(resource, {}).update(summary)
        return {
            "enabled": True,
            "slots": self.llm_slot_count,
            "llmSlots": self.llm_slot_count,
            "cudaSlots": self.cuda_slot_count,
            "ocrSlots": self.ocr_slot_count,
            "adaptiveSlots": adaptive_slots,
            "detectedGpus": self.detected_gpu_count,
            "processId": self.process_id,
            "queueTimeoutSeconds": self.queue_timeout_seconds,
            "active": counts.get("running", 0),
            "queued": counts.get("queued", 0),
            "completed": counts.get("completed", 0),
            "failed": counts.get("failed", 0),
            "timedOut": counts.get("timed_out", 0),
            "wait": wait_summary.get("overall", {}),
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
            "admittedSlots": self._effective_slot_count_for(resource_class, running_slots=running),
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
                dead_pids = self._dead_gpu_work_process_ids(conn)
                if dead_pids:
                    conn.execute(load_query("local_gpu_work_cleanup_dead_processes.sql"), (dead_pids,))
                    if self.logger:
                        self.logger.warning(
                            "⚠️ Recovered local GPU work owned by dead process IDs: "
                            + ", ".join(str(pid) for pid in sorted(dead_pids))
                        )
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

    def _dead_gpu_work_process_ids(self, conn) -> list[int]:
        rows = conn.execute(load_query("local_gpu_work_live_process_ids.sql")).fetchall()
        dead: list[int] = []
        for row in rows:
            pid = row.get("process_id")
            if pid is None:
                continue
            pid = int(pid)
            if pid <= 0:
                continue
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                dead.append(pid)
            except PermissionError:
                continue
            except Exception:
                continue
        return dead

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

            effective_slot_count = self._effective_slot_count_for(resource_class)
            if not self._task_is_eligible(task_id, effective_slot_count):
                time.sleep(self.poll_seconds)
                continue

            for slot_index in range(effective_slot_count):
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
                    return conn, slot_index, wait_seconds, effective_slot_count
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

    def _task_is_eligible(self, task_id: str, slot_count: int) -> bool:
        with self.database.connection() as conn:
            row = conn.execute(
                load_query("local_gpu_work_eligible.sql"),
                (max(1, int(slot_count or 1)), task_id),
            ).fetchone()
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

    def _effective_slot_count_for(self, resource_class: str, *, running_slots: int = 0) -> int:
        if resource_class != "ocr_cuda":
            return self._slot_count_for(resource_class)
        return self._adaptive_ocr_slot_count(running_slots=running_slots)["activeSlots"]

    def _adaptive_slots_payload(self, *, running_by_resource: dict[str, int] | None = None) -> dict[str, Any]:
        running_by_resource = running_by_resource or {}
        return {"ocr_cuda": self._adaptive_ocr_slot_count(running_slots=running_by_resource.get("ocr_cuda", 0))}

    def _adaptive_ocr_slot_count(self, *, running_slots: int = 0) -> dict[str, Any]:
        payload = resolve_adaptive_ocr_slots(
            self._slot_count_for("ocr_cuda"),
            self._cached_gpu_pressure(),
            running_slots=running_slots,
        )
        return self._stabilize_adaptive_ocr_slots(payload)

    def _stabilize_adaptive_ocr_slots(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Smooth OCR lane changes so telemetry noise does not churn the queue.

        OCR admission should use all configured lanes while there is headroom,
        back off immediately for hard thermal/VRAM guards, and otherwise reduce
        capacity only after sustained pressure. The result is still capped by
        the detected hardware-derived max slot count.
        """
        if not payload.get("enabled"):
            return payload

        max_slots = max(1, int(payload.get("maxSlots") or self.ocr_slot_count or 1))
        proposed_target = max(1, min(max_slots, int(payload.get("targetSlots") or max_slots)))
        running_slots = max(0, min(max_slots, int(payload.get("runningSlots") or 0)))
        pressure_level = str(payload.get("pressureLevel") or "")
        hard_guard = pressure_level == "hard"
        with self._ocr_adaptive_lock:
            current_target = self._ocr_target_slots
            if current_target is None or current_target > max_slots:
                current_target = max_slots

            if proposed_target < current_target:
                if hard_guard:
                    target = proposed_target
                    self._ocr_pressure_strikes = 0
                else:
                    self._ocr_pressure_strikes += 1
                    target = current_target
                    if self._ocr_pressure_strikes >= 3:
                        target = proposed_target
                        self._ocr_pressure_strikes = 0
                    else:
                        payload["reason"] = (
                            f"{payload.get('reason')}; waiting for sustained pressure "
                            f"({self._ocr_pressure_strikes}/3)"
                        )
            elif proposed_target > current_target:
                target = proposed_target
                self._ocr_pressure_strikes = 0
            else:
                target = current_target
                if pressure_level == "headroom":
                    self._ocr_pressure_strikes = 0

            self._ocr_target_slots = max(1, min(max_slots, target))
            payload["targetSlots"] = self._ocr_target_slots
            payload["activeSlots"] = max(self._ocr_target_slots, running_slots)
            payload["pressureStrikes"] = self._ocr_pressure_strikes
            payload["rawTargetSlots"] = proposed_target
        return payload

    @staticmethod
    def _running_counts_by_resource(rows: list[dict[str, Any]]) -> dict[str, int]:
        running: dict[str, int] = {}
        for row in rows:
            if str(row.get("status") or "") != "running":
                continue
            resource = str(row.get("resource_class") or "unknown")
            running[resource] = running.get(resource, 0) + int(row.get("count") or 0)
        return running

    def _cached_gpu_pressure(self, *, max_age_seconds: float = 1.0) -> dict[str, Any]:
        now = time.monotonic()
        with self._pressure_lock:
            if self._pressure_sample and (now - self._pressure_sample[0]) <= max_age_seconds:
                return dict(self._pressure_sample[1])
            pressure = read_local_gpu_pressure()
            self._pressure_sample = (now, dict(pressure))
            return pressure

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

    @classmethod
    def _wait_summary_payload(cls, rows: list[dict[str, Any]]) -> dict[str, Any]:
        by_resource: dict[str, dict[str, float | int | None]] = {}
        overall: dict[str, float | int | None] = {}
        for row in rows:
            resource = str(row.get("resource_class") or "unknown")
            payload = {
                "queued": int(row.get("queued") or 0),
                "running": int(row.get("running") or 0),
                "currentAvgWaitSeconds": _optional_float(row.get("current_avg_wait_seconds")),
                "currentMaxWaitSeconds": _optional_float(row.get("current_max_wait_seconds")),
                "recentAvgWaitSeconds": _optional_float(row.get("recent_avg_wait_seconds")),
                "recentMaxWaitSeconds": _optional_float(row.get("recent_max_wait_seconds")),
            }
            if resource == "all":
                overall = payload
            else:
                by_resource[resource] = payload
        return {"overall": overall, "byResource": by_resource}

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
