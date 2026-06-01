import os
import tempfile
import time


class IngestHousekeepingService:
    def __init__(
        self,
        *,
        config,
        trace_logger,
        cleanup_old_logs,
        trace_log_file: str,
        active_trace_log_file,
        log_retention_days: int,
        tesseract_temp_max_age_seconds: int,
    ):
        self.config = config
        self.trace_logger = trace_logger
        self.cleanup_old_logs = cleanup_old_logs
        self.trace_log_file = trace_log_file
        self.active_trace_log_file = active_trace_log_file
        self.log_retention_days = log_retention_days
        self.tesseract_temp_max_age_seconds = tesseract_temp_max_age_seconds

    def cleanup_stale_tesseract_temp_files(self, max_age_seconds=None) -> dict:
        max_age_seconds = max_age_seconds or self.tesseract_temp_max_age_seconds
        temp_dir = tempfile.gettempdir()
        now = time.time()
        removed = 0
        failures = 0

        try:
            names = os.listdir(temp_dir)
        except OSError as exc:
            self.trace_logger.warning(f"Could not inspect temp directory for stale Tesseract files: {exc}")
            return {"removed": 0, "failures": 1}

        for filename in names:
            if not filename.startswith("tess_"):
                continue
            path = os.path.join(temp_dir, filename)
            try:
                if not os.path.isfile(path):
                    continue
                if now - os.path.getmtime(path) < max_age_seconds:
                    continue
                os.remove(path)
                removed += 1
            except OSError as exc:
                failures += 1
                self.trace_logger.debug(f"Could not remove stale Tesseract temp file {path}: {exc}")
        if removed or failures:
            self.trace_logger.info(
                f"Cleaned stale Tesseract temp files. Removed: {removed}, failures: {failures}"
            )
        return {"removed": removed, "failures": failures}

    def cleanup_expired_trace_logs(self):
        return self.cleanup_old_logs(
            configured_log_file=self.trace_log_file,
            active_log_file=self.active_trace_log_file(),
            retention_days=self.log_retention_days,
            logger=self.trace_logger,
        )

    def run_index_housekeeping(self) -> None:
        try:
            self.cleanup_stale_tesseract_temp_files()
        except Exception as exc:
            self.trace_logger.warning(f"Index housekeeping could not clean stale Tesseract temp files: {exc}")

        try:
            self.cleanup_expired_trace_logs()
        except Exception as exc:
            self.trace_logger.warning(f"Index housekeeping could not clean expired trace logs: {exc}")
