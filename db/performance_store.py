from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from typing import Any

from psycopg.errors import UndefinedTable

from db.connection import Database
from db.sql import load_query


class PerformanceStore:
    def __init__(self, database: Database, logger=None, *, sample_interval_seconds: int = 5):
        self.database = database
        self.logger = logger
        self.sample_interval_seconds = max(1, int(sample_interval_seconds))
        self._last_sample_at = 0.0
        self._sample_lock = threading.Lock()

    def available(self) -> bool:
        if not self.database.configured:
            return False
        try:
            with self.database.connection() as conn:
                conn.execute(load_query("performance_resource_samples_recent.sql"), (1, 1))
            return True
        except UndefinedTable:
            return False
        except Exception as exc:
            if self.logger:
                self.logger.warning(f"Performance store is not available: {exc}")
            return False

    def record_resource_sample(self, status: dict[str, Any]) -> None:
        if not self.database.configured:
            return
        now = time.monotonic()
        with self._sample_lock:
            if now - self._last_sample_at < self.sample_interval_seconds:
                return
            self._last_sample_at = now

        resources = status.get("systemResources") or {}
        cpu = resources.get("cpu") or {}
        memory = resources.get("memory") or {}
        process = resources.get("process") or {}
        gpu = resources.get("gpu") or {}
        worker_budget = status.get("ingestWorkerBudget") or {}
        batches = status.get("runtimeBatches") or {}
        embedding = batches.get("embedding") or {}
        reranker = batches.get("reranker") or {}
        try:
            with self.database.connection() as conn:
                conn.execute(
                    load_query("performance_resource_sample_insert.sql"),
                    (
                        self._optional_float(cpu.get("utilizationPercent")),
                        self._optional_float(process.get("cpuPercent")),
                        self._optional_int(process.get("memoryBytes")),
                        self._optional_int(process.get("threads")),
                        self._optional_float(memory.get("usedPercent")),
                        self._optional_float(gpu.get("utilizationPercent")) if gpu.get("available") else None,
                        self._optional_float(gpu.get("memoryUsedPercent")) if gpu.get("available") else None,
                        self._optional_float(gpu.get("memoryUsedMiB")) if gpu.get("available") else None,
                        self._optional_float(gpu.get("memoryTotalMiB")) if gpu.get("available") else None,
                        self._optional_float(gpu.get("temperatureC")) if gpu.get("available") else None,
                        self._optional_float(gpu.get("powerW")) if gpu.get("available") else None,
                        self._optional_int(worker_budget.get("activeDocumentWorkers")) or 0,
                        self._optional_int(embedding.get("active")) or 0,
                        self._optional_int(reranker.get("active")) or 0,
                        self._optional_int(status.get("chunks")) or 0,
                        self._optional_int(status.get("sources")) or 0,
                        self._optional_int(status.get("imageIds")) or 0,
                    ),
                )
        except UndefinedTable:
            return
        except Exception as exc:
            if self.logger:
                self.logger.warning(f"Performance sample write failed: {exc}")

    def record_work_run(
        self,
        *,
        work_type: str,
        label: str,
        trigger_reason: str = "",
        status: str = "completed",
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
        duration_ms: int = 0,
        entity_id: int | None = None,
        user_id: int | None = None,
        source_path: str = "",
        chunks: int = 0,
        images: int = 0,
        dropped_chunks: int = 0,
        details: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> None:
        if not self.database.configured:
            return
        started = started_at or datetime.now(timezone.utc)
        finished = finished_at or datetime.now(timezone.utc)
        if not duration_ms:
            duration_ms = max(0, int((finished - started).total_seconds() * 1000))
        try:
            with self.database.connection() as conn:
                row = conn.execute(load_query("performance_work_type_id.sql"), (work_type,)).fetchone()
                work_type_id = row["id"] if row else None
                conn.execute(
                    load_query("performance_work_run_insert.sql"),
                    (
                        work_type_id,
                        entity_id,
                        user_id,
                        label,
                        trigger_reason,
                        status,
                        source_path,
                        started,
                        finished,
                        int(duration_ms),
                        int(chunks or 0),
                        int(images or 0),
                        int(dropped_chunks or 0),
                        json.dumps(details or {}, default=str),
                        error_message,
                    ),
                )
        except UndefinedTable:
            return
        except Exception as exc:
            if self.logger:
                self.logger.warning(f"Performance work-run write failed: {exc}")

    def report(self, *, hours: int = 24, sample_limit: int = 300, work_limit: int = 80) -> dict[str, Any]:
        if not self.database.configured:
            return {"samples": [], "recentWork": [], "available": False}
        try:
            with self.database.connection() as conn:
                sample_rows = conn.execute(
                    load_query("performance_resource_samples_recent.sql"),
                    (max(1, int(hours)), max(1, int(sample_limit))),
                ).fetchall()
                work_rows = conn.execute(
                    load_query("performance_work_runs_recent.sql"),
                    (max(1, int(hours)), max(1, int(work_limit))),
                ).fetchall()
            samples = [self._sample_row(row) for row in reversed(sample_rows)]
            recent_work = [self._work_row(row) for row in work_rows]
            return {"samples": samples, "recentWork": recent_work, "available": True}
        except UndefinedTable:
            return {"samples": [], "recentWork": [], "available": False}
        except Exception as exc:
            if self.logger:
                self.logger.warning(f"Performance report failed: {exc}")
            return {"samples": [], "recentWork": [], "available": False, "error": str(exc)}

    @staticmethod
    def _sample_row(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "sampledAt": row["sampled_at"].isoformat() if row.get("sampled_at") else None,
            "cpu": PerformanceStore._optional_float(row.get("cpu_percent")),
            "processCpu": PerformanceStore._optional_float(row.get("process_cpu_percent")),
            "processMemoryBytes": PerformanceStore._optional_int(row.get("process_memory_bytes")),
            "processThreads": PerformanceStore._optional_int(row.get("process_threads")),
            "ram": PerformanceStore._optional_float(row.get("system_memory_used_percent")),
            "gpu": PerformanceStore._optional_float(row.get("gpu_percent")),
            "vram": PerformanceStore._optional_float(row.get("gpu_memory_used_percent")),
            "gpuMemoryUsedMiB": PerformanceStore._optional_float(row.get("gpu_memory_used_mib")),
            "gpuMemoryTotalMiB": PerformanceStore._optional_float(row.get("gpu_memory_total_mib")),
            "gpuTemperatureC": PerformanceStore._optional_float(row.get("gpu_temperature_c")),
            "gpuPowerW": PerformanceStore._optional_float(row.get("gpu_power_w")),
            "workers": PerformanceStore._optional_int(row.get("active_document_workers")) or 0,
            "embeddingBatch": PerformanceStore._optional_int(row.get("embedding_batch_active")) or 0,
            "rerankerBatch": PerformanceStore._optional_int(row.get("reranker_batch_active")) or 0,
            "chunks": PerformanceStore._optional_int(row.get("chunks")) or 0,
            "sources": PerformanceStore._optional_int(row.get("sources")) or 0,
            "images": PerformanceStore._optional_int(row.get("image_ids")) or 0,
        }

    @staticmethod
    def _work_row(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row.get("id"),
            "workType": row.get("work_type") or "unknown",
            "workTypeLabel": row.get("work_type_label") or "Unknown",
            "entityId": row.get("entity_id"),
            "entityName": row.get("entity_name"),
            "userId": row.get("user_id"),
            "username": row.get("username"),
            "label": row.get("label") or "",
            "triggerReason": row.get("trigger_reason") or "",
            "status": row.get("status") or "",
            "sourcePath": row.get("source_path") or "",
            "startedAt": row["started_at"].isoformat() if row.get("started_at") else None,
            "finishedAt": row["finished_at"].isoformat() if row.get("finished_at") else None,
            "durationMs": PerformanceStore._optional_int(row.get("duration_ms")) or 0,
            "chunks": PerformanceStore._optional_int(row.get("chunks")) or 0,
            "images": PerformanceStore._optional_int(row.get("images")) or 0,
            "droppedChunks": PerformanceStore._optional_int(row.get("dropped_chunks")) or 0,
            "details": row.get("details") or {},
            "errorMessage": row.get("error_message"),
        }

    @staticmethod
    def _optional_float(value: Any) -> float | None:
        try:
            return None if value is None else float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _optional_int(value: Any) -> int | None:
        try:
            return None if value is None else int(value)
        except (TypeError, ValueError):
            return None
