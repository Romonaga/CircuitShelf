import threading
from datetime import datetime, timezone


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def utc_now():
    return datetime.now(timezone.utc)


class IngestProgressTracker:
    def __init__(self, *, config, status_callback=None):
        self.config = config
        self.status_callback = status_callback
        self.status = {
            "enabled": bool(config.get("INGEST_WATCH_ENABLED", True)),
            "running": False,
            "stage": "idle",
            "currentFiles": [],
            "fileProgress": {},
            "processedFiles": 0,
            "totalFiles": 0,
            "lastStartedAt": None,
            "lastFinishedAt": None,
            "lastReason": None,
            "lastResult": "idle",
            "lastError": None,
            "lastChanges": None,
            "nextCheckAt": None,
            "details": {},
        }
        self._status_lock = threading.Lock()
        self._worker_lock = threading.Lock()
        self._active_workers = 0

    def _notify_status(self, status):
        if not self.status_callback:
            return
        try:
            self.status_callback(dict(status))
        except Exception:
            # Progress persistence must not destabilize ingestion.
            return

    def set_status(self, **updates):
        with self._status_lock:
            self.status.update(updates)
            snapshot = dict(self.status)
        self._notify_status(snapshot)
        return snapshot

    def watch_interval_seconds(self) -> int:
        return max(30, int(self.config.get("INGEST_WATCH_INTERVAL_SECONDS", 300)))

    def schedule_next_check(self, interval=None):
        interval_seconds = interval if interval is not None else self.watch_interval_seconds()
        next_check = datetime.now(timezone.utc).timestamp() + interval_seconds
        return self.set_status(
            nextCheckAt=datetime.fromtimestamp(next_check, timezone.utc).isoformat()
        )

    def seconds_until_next_check(self, interval=None) -> float:
        with self._status_lock:
            next_check_at = self.status.get("nextCheckAt")
        if not next_check_at:
            status = self.schedule_next_check(interval)
            next_check_at = status["nextCheckAt"]
        try:
            next_check = datetime.fromisoformat(next_check_at).timestamp()
        except (TypeError, ValueError):
            status = self.schedule_next_check(interval)
            next_check = datetime.fromisoformat(status["nextCheckAt"]).timestamp()
        return max(0, next_check - datetime.now(timezone.utc).timestamp())

    def update_progress(
        self,
        *,
        stage=None,
        current_file=None,
        finished_file=None,
        total_files=None,
        details=None,
        file_details=None,
    ):
        with self._status_lock:
            active_files = list(self.status.get("currentFiles") or [])
            file_progress = dict(self.status.get("fileProgress") or {})
            if total_files is not None:
                self.status["totalFiles"] = int(total_files)
            if stage is not None:
                self.status["stage"] = stage
            if details is not None:
                self.status["details"] = details
            if current_file and current_file not in active_files:
                active_files.append(current_file)
                file_progress.setdefault(current_file, {})
            if current_file and file_details is not None:
                current_progress = dict(file_progress.get(current_file) or {})
                current_progress.update({key: value for key, value in file_details.items() if value is not None})
                file_progress[current_file] = current_progress
            if finished_file:
                active_files = [name for name in active_files if name != finished_file]
                file_progress.pop(finished_file, None)
                self.status["processedFiles"] = int(self.status.get("processedFiles") or 0) + 1
            self.status["currentFiles"] = active_files
            self.status["fileProgress"] = {name: file_progress.get(name, {}) for name in active_files}
            snapshot = dict(self.status)
        self._notify_status(snapshot)
        return snapshot

    def update_detail(self, **updates):
        with self._status_lock:
            details = dict(self.status.get("details") or {})
            details.update({key: value for key, value in updates.items() if value is not None})
            self.status["details"] = details
            snapshot = dict(self.status)
        self._notify_status(snapshot)
        return snapshot

    def snapshot(self) -> dict:
        with self._status_lock:
            return dict(self.status)

    def begin_document_worker(self) -> int:
        with self._worker_lock:
            self._active_workers += 1
            return self._active_workers

    def finish_document_worker(self) -> int:
        with self._worker_lock:
            self._active_workers = max(0, self._active_workers - 1)
            return self._active_workers

    def current_document_workers(self) -> int:
        with self._worker_lock:
            return max(1, self._active_workers)

    def active_document_worker_count(self) -> int:
        with self._worker_lock:
            return self._active_workers
