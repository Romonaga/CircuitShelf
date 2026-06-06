from __future__ import annotations

import os
import signal
import time
from dataclasses import dataclass
from typing import Any

from backend.services.model_runtime import release_accelerator_memory


@dataclass
class IngestWorkerRunner:
    runtime: Any
    job_store: Any
    trace_logger: Any
    poll_interval_seconds: float = 1.0
    settings_store: Any = None
    runtime_settings: Any = None
    settings_refresh_seconds: float = 15.0

    def __post_init__(self):
        self._stop = False
        self._last_settings_refresh = 0.0

    def request_stop(self, *_args):
        self._stop = True

    def install_signal_handlers(self):
        signal.signal(signal.SIGTERM, self.request_stop)
        signal.signal(signal.SIGINT, self.request_stop)

    def run_forever(self):
        self.install_signal_handlers()
        self.trace_logger.info("👷 CircuitShelf ingestion worker started.")
        self._initialize_runtime()
        try:
            while not self._stop:
                self._refresh_runtime_settings()
                self._maybe_enqueue_watch_check()
                job = self.job_store.claim_next(worker_pid=os.getpid())
                if not job:
                    time.sleep(self.poll_interval_seconds)
                    continue
                self._run_job(job)
        finally:
            release_accelerator_memory(self.trace_logger)
            self.runtime.runtime_status_reporter.stop_resource_sampler()
            self.trace_logger.info("👷 CircuitShelf ingestion worker stopped.")

    def _refresh_runtime_settings(self):
        if not self.settings_store or not self.runtime_settings:
            return
        now = time.monotonic()
        if now - self._last_settings_refresh < self.settings_refresh_seconds:
            return
        self._last_settings_refresh = now
        try:
            self.runtime_settings.refresh_from_store(self.settings_store)
        except Exception as exc:
            self.trace_logger.warning(f"⚠️ Ingest worker settings refresh failed: {exc}")

    def _initialize_runtime(self):
        self.runtime.cleanup_stale_tesseract_temp_files()
        self.runtime.get_or_build_index()
        self.runtime.runtime_status_reporter.start_resource_sampler()
        self._recover_abandoned_jobs()
        self.runtime.ingest_progress.schedule_next_check()
        self.runtime.unload_idle_gpu_models()
        release_accelerator_memory(self.trace_logger)

    def _recover_abandoned_jobs(self):
        recovered = self.job_store.recover_abandoned_running(worker_pid=os.getpid())
        if not recovered:
            return
        reasons = [str(job.get("reason") or "unknown") for job in recovered]
        self.trace_logger.warning(
            f"⚠️ Recovered {len(recovered)} abandoned ingest job(s) after worker restart: {', '.join(reasons[:5])}"
        )
        self.runtime.ingest_progress.set_status(
            running=False,
            stage="failed",
            currentFiles=[],
            fileProgress={},
            lastFinishedAt=self.runtime.ingest_progress.snapshot().get("lastFinishedAt"),
            lastResult="worker_restarted",
            lastError="Previous ingest worker exited before its running job completed.",
            details={
                "recoveredAbandonedJobs": len(recovered),
                "recoveredReasons": reasons[:10],
            },
        )
        counts = self.job_store.counts()
        if counts.get("queued", 0) or counts.get("running", 0):
            return
        self.job_store.enqueue(
            "crash-recovery",
            details={
                "requestedFrom": "ingest-worker-startup",
                "recoveredJobIds": [job.get("id") for job in recovered],
                "recoveredReasons": reasons[:10],
            },
        )
        self.trace_logger.info("🔁 Queued crash-recovery ingest scan after abandoned job cleanup.")

    def _maybe_enqueue_watch_check(self):
        if not self.runtime.config.get("INGEST_WATCH_ENABLED", True):
            self.runtime.ingest_progress.set_status(enabled=False)
            return
        if self.runtime.index_lifecycle_service.seconds_until_next_ingest_check() > 0:
            return
        self.runtime.index_lifecycle_service.schedule_next_ingest_check()
        queued = self.job_store.counts().get("queued", 0)
        running = self.job_store.counts().get("running", 0)
        if queued or running:
            return
        self.job_store.enqueue("watch", details={"requestedFrom": "ingest-worker"})

    def _run_job(self, job: dict[str, Any]):
        job_id = int(job["id"])
        reason = job.get("reason") or "queued"
        if reason != "watch":
            self.trace_logger.info(f"▶️ Ingest worker claimed job {job_id}: {reason}")
        started = time.time()
        try:
            if str(reason).startswith("reindex:"):
                source = str(reason).split(":", 1)[1].strip()
                if not source:
                    raise ValueError("Reindex job is missing a source path.")
                self.runtime.incremental_ingest_service.reindex_review_source(source)
            else:
                self.runtime.index_lifecycle_service.check_for_training_changes(reason=reason)
            snapshot = self.runtime.ingest_progress.snapshot()
            result = snapshot.get("lastResult") or "completed"
            status = "skipped" if result in {"no_changes", "already_running"} else "completed"
            self.job_store.finish(job_id, status=status, details=snapshot)
            if status != "skipped" or reason != "watch":
                self.trace_logger.info(
                    f"✅ Ingest worker finished job {job_id}: {reason} "
                    f"status={status} result={result} duration={time.time() - started:.2f}s"
                )
        except Exception as exc:
            snapshot = self.runtime.ingest_progress.snapshot()
            self.job_store.finish(job_id, status="failed", error=str(exc), details=snapshot)
            self.trace_logger.error(f"❌ Ingest worker failed job {job_id}: {reason}: {exc}")
        finally:
            self.runtime.unload_idle_gpu_models()
            release_accelerator_memory(self.trace_logger)
