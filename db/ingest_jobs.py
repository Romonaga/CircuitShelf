from __future__ import annotations

import json
from typing import Any

from psycopg.errors import UndefinedTable

from db.connection import Database
from db.sql import load_query


class IngestJobStore:
    def __init__(self, database: Database, logger=None):
        self.database = database
        self.logger = logger

    def available(self) -> bool:
        if not self.database.configured:
            return False
        try:
            with self.database.connection() as conn:
                conn.execute(load_query("ingest_jobs_counts.sql")).fetchall()
            return True
        except UndefinedTable:
            return False
        except Exception as exc:
            if self.logger:
                self.logger.warning(f"Ingest job store is not available: {exc}")
            return False

    def enqueue(self, reason: str, *, requested_by_user_id: int | None = None, details: dict[str, Any] | None = None) -> dict[str, Any]:
        with self.database.connection() as conn:
            row = conn.execute(
                load_query("ingest_job_enqueue.sql"),
                (
                    str(reason or "manual"),
                    requested_by_user_id,
                    json.dumps(details or {}, default=str),
                ),
            ).fetchone()
        status = self.get_status()
        return {
            "started": True,
            "queued": True,
            "jobId": row["id"],
            "reason": row["reason"],
            "status": status,
        }

    def claim_next(self, *, worker_pid: int) -> dict[str, Any] | None:
        with self.database.connection() as conn:
            row = conn.execute(load_query("ingest_job_claim_next.sql"), (int(worker_pid),)).fetchone()
        return dict(row) if row else None

    def finish(
        self,
        job_id: int,
        *,
        status: str,
        error: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        with self.database.connection() as conn:
            row = conn.execute(
                load_query("ingest_job_finish.sql"),
                (
                    error,
                    json.dumps(details or {}, default=str),
                    int(job_id),
                    str(status),
                ),
            ).fetchone()
        return dict(row) if row else None

    def counts(self) -> dict[str, int]:
        try:
            with self.database.connection() as conn:
                rows = conn.execute(load_query("ingest_jobs_counts.sql")).fetchall()
            return {str(row["code"]): int(row["count"] or 0) for row in rows}
        except UndefinedTable:
            return {}

    def recent(self, *, limit: int = 20) -> list[dict[str, Any]]:
        try:
            with self.database.connection() as conn:
                rows = conn.execute(load_query("ingest_jobs_recent.sql"), (max(1, int(limit)),)).fetchall()
            return [self._job_row(row) for row in rows]
        except UndefinedTable:
            return []

    def save_status(self, status: dict[str, Any]) -> None:
        if not self.database.configured:
            return
        try:
            with self.database.connection() as conn:
                conn.execute(load_query("ingest_runtime_status_upsert.sql"), (json.dumps(status, default=str),))
        except UndefinedTable:
            return
        except Exception as exc:
            if self.logger:
                self.logger.warning(f"Ingest status write failed: {exc}")

    def get_status(self) -> dict[str, Any]:
        status = None
        updated_at = None
        try:
            with self.database.connection() as conn:
                row = conn.execute(load_query("ingest_runtime_status_get.sql")).fetchone()
            if row:
                status = row.get("status") or {}
                updated_at = row.get("updated_at")
        except UndefinedTable:
            status = {}
        status = dict(status or {})
        details = dict(status.get("details") or {})
        details["queuedJobs"] = self.counts().get("queued", 0)
        status["details"] = details
        if updated_at:
            status["updatedAt"] = updated_at.isoformat()
        return status

    @staticmethod
    def _job_row(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row.get("id"),
            "reason": row.get("reason") or "",
            "status": row.get("status") or "",
            "requestedByUserId": row.get("requested_by_user_id"),
            "requestedByUsername": row.get("requested_by_username"),
            "workerPid": row.get("worker_pid"),
            "createdAt": row["created_at"].isoformat() if row.get("created_at") else None,
            "startedAt": row["started_at"].isoformat() if row.get("started_at") else None,
            "finishedAt": row["finished_at"].isoformat() if row.get("finished_at") else None,
            "lastError": row.get("last_error"),
            "details": row.get("details") or {},
        }
