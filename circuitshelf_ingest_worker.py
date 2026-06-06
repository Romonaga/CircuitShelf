from __future__ import annotations

from backend.bootstrap_runtime import bootstrap_runtime
from backend.native_faults import enable_native_fault_diagnostics
from backend.workers.ingest_worker import IngestWorkerRunner
from backend.services.process_lock import ProcessLockError, acquire_process_lock


enable_native_fault_diagnostics()

boot = bootstrap_runtime(
    ingest_status_callback=lambda status: boot.stores.ingest_job_store.save_status(status) if "boot" in globals() else None,
    ingest_status_provider=lambda: boot.stores.ingest_job_store.get_status() if "boot" in globals() else {},
    lazy_gpu_models=True,
)


if __name__ == "__main__":
    pid_file = boot.config.get("INGEST_WORKER_PID_FILE", "data/circuitshelf-ingest.pid")
    try:
        with acquire_process_lock(pid_file, name="CircuitShelf ingest worker"):
            IngestWorkerRunner(
                runtime=boot.runtime,
                job_store=boot.stores.ingest_job_store,
                trace_logger=boot.trace_logger,
                poll_interval_seconds=float(boot.config.get("INGEST_WORKER_POLL_SECONDS", 1.0) or 1.0),
                settings_store=boot.settings_store,
                runtime_settings=boot.runtime_settings,
            ).run_forever()
    except ProcessLockError as exc:
        boot.trace_logger.error(str(exc))
        raise SystemExit(1) from exc
