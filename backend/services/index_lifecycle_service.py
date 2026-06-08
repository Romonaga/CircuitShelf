import os
import threading
import time

from backend.domain.statuses import PerformanceWorkStatusId
from backend.services.upload_session_guard import active_upload_sessions


class IndexLifecycleService:
    def __init__(
        self,
        *,
        config,
        trace_logger,
        state,
        vector_store,
        image_store,
        performance_store,
        training_dir: str,
        build_ingest_manifest,
        run_incremental_ingest,
        file_changes_payload,
        set_index_status,
        schedule_next_ingest_check,
        seconds_until_next_ingest_check,
        ingest_watch_interval_seconds,
        index_status,
        ingest_progress,
        run_index_housekeeping,
        load_db_image_state,
        backfill_missing_image_embeddings,
        system_log_build_info,
        utc_now,
        utc_now_iso,
    ):
        self.config = config
        self.trace_logger = trace_logger
        self.state = state
        self.vector_store = vector_store
        self.image_store = image_store
        self.performance_store = performance_store
        self.training_dir = training_dir
        self.build_ingest_manifest = build_ingest_manifest
        self.run_incremental_ingest = run_incremental_ingest
        self.file_changes_payload = file_changes_payload
        self.set_index_status = set_index_status
        self.schedule_next_ingest_check = schedule_next_ingest_check
        self.seconds_until_next_ingest_check = seconds_until_next_ingest_check
        self.ingest_watch_interval_seconds = ingest_watch_interval_seconds
        self.index_status = index_status
        self.ingest_progress = ingest_progress
        self.run_index_housekeeping = run_index_housekeeping
        self.load_db_image_state = load_db_image_state
        self.backfill_missing_image_embeddings = backfill_missing_image_embeddings
        self.system_log_build_info = system_log_build_info
        self.utc_now = utc_now
        self.utc_now_iso = utc_now_iso
        self._index_job_lock = threading.Lock()
        self._watch_stop = threading.Event()
        self._watch_reschedule = threading.Event()
        self._watch_thread = None

    def check_for_training_changes(self, reason="watch"):
        if not self._index_job_lock.acquire(blocking=False):
            self.trace_logger.info(f"⏳ Index check skipped for {reason}; another index job is running.")
            self.performance_store.record_work_run(
                work_type="index_check",
                label="Index check skipped",
                trigger_reason=reason,
                status=PerformanceWorkStatusId.SKIPPED,
                details={"reason": "already_running"},
            )
            return self.set_index_status(lastResult="already_running")

        started_at = self.utc_now()
        work_status = PerformanceWorkStatusId.COMPLETED
        work_label = "Index check"
        work_error = None
        work_details = {}
        self.set_index_status(
            running=True,
            stage="scanning",
            currentFiles=[],
            fileProgress={},
            processedFiles=0,
            totalFiles=0,
            lastStartedAt=self.utc_now_iso(),
            lastFinishedAt=None,
            lastReason=reason,
            lastError=None,
            lastResult="running",
            lastChanges=None,
            details={},
        )
        start_time = time.time()
        try:
            active_uploads = active_upload_sessions(self.training_dir)
            if active_uploads:
                if reason != "watch":
                    self.trace_logger.info(
                        f"⏳ Index check deferred for {reason}; {len(active_uploads)} upload session(s) still active."
                    )
                work_label = "Index check: upload active"
                work_status = PerformanceWorkStatusId.SKIPPED
                work_details = {"reason": "upload_in_progress", "activeUploadSessions": len(active_uploads)}
                return self.set_index_status(
                    running=False,
                    stage="idle",
                    currentFiles=[],
                    fileProgress={},
                    processedFiles=0,
                    totalFiles=0,
                    lastFinishedAt=self.utc_now_iso(),
                    lastResult="upload_in_progress",
                    lastChanges=None,
                    details=work_details,
                )

            manifest = self.build_ingest_manifest()
            current_manifest = manifest.scan()
            previous_manifest = self.vector_store.load_document_records()
            changes = manifest.diff(previous_manifest, current_manifest)
            self.set_index_status(lastChanges=self.file_changes_payload(changes))
            if not changes.has_changes:
                if reason != "watch":
                    self.trace_logger.info(f"✅ Index check found no training changes for {reason}.")
                work_label = "Index check: no changes"
                work_status = PerformanceWorkStatusId.SKIPPED
                work_details = self.file_changes_payload(changes)
                return self.set_index_status(
                    running=False,
                    stage="idle",
                    currentFiles=[],
                    fileProgress={},
                    processedFiles=0,
                    totalFiles=0,
                    lastFinishedAt=self.utc_now_iso(),
                    lastResult="no_changes",
                    lastChanges=self.file_changes_payload(changes),
                    details={},
                )

            self.set_index_status(
                stage="processing_documents",
                processedFiles=0,
                totalFiles=len(changes.changed_or_added),
                currentFiles=[],
                fileProgress={},
            )
            build_result, final_details = self.run_incremental_ingest(changes, current_manifest)
            duration = time.time() - start_time
            self.trace_logger.info(
                f"✅ Ingest run finished: reason={reason} duration={duration:.2f}s "
                f"files={len(changes.changed_or_added)} chunks={int(final_details.get('chunks') or 0)} "
                f"dropped={int(final_details.get('droppedChunks') or 0)} "
                f"images={int(final_details.get('storedImages') or final_details.get('extractedImages') or 0)} "
                f"failed={int(final_details.get('failedDocuments') or 0)} "
                f"catalog_chunks={len(self.state.get_chunks())} embeddings={len(self.state.get_embeddings())}"
            )
            result = "updated"
            if build_result:
                result = f"review_ready {build_result.chunks} changed chunks"
                work_label = "Document ingest"
                work_details = final_details
            elif changes.removed and not changes.changed_or_added:
                result = f"ignored {len(changes.removed)} missing source files"
                work_label = "Index check: ignored missing sources"
                work_status = PerformanceWorkStatusId.SKIPPED
                work_details = final_details
            else:
                work_details = final_details
            return self.set_index_status(
                running=False,
                stage="idle",
                currentFiles=[],
                fileProgress={},
                processedFiles=len(changes.changed_or_added),
                totalFiles=len(changes.changed_or_added),
                lastFinishedAt=self.utc_now_iso(),
                lastResult=result,
                lastChanges=self.file_changes_payload(changes),
                details=final_details,
            )
        except Exception as exc:
            self.trace_logger.error(f"❌ Incremental index check failed for {reason}: {exc}")
            work_status = PerformanceWorkStatusId.FAILED
            work_label = "Index check failed"
            work_error = str(exc)
            return self.set_index_status(
                running=False,
                stage="failed",
                currentFiles=[],
                fileProgress={},
                lastFinishedAt=self.utc_now_iso(),
                lastResult="failed",
                lastError=str(exc),
                details={},
            )
        finally:
            finished_at = self.utc_now()
            index_snapshot = self.ingest_progress.snapshot()
            detail_snapshot = dict(index_snapshot.get("details") or {})
            last_changes = index_snapshot.get("lastChanges")
            merged_details = {
                **(work_details or {}),
                **detail_snapshot,
                "lastChanges": last_changes,
            }
            self.performance_store.record_work_run(
                work_type="document_ingest" if work_label == "Document ingest" else "index_check",
                label=work_label,
                trigger_reason=reason,
                status=work_status,
                started_at=started_at,
                finished_at=finished_at,
                chunks=int(merged_details.get("chunks") or 0),
                images=int(merged_details.get("storedImages") or merged_details.get("extractedImages") or 0),
                dropped_chunks=int(merged_details.get("droppedChunks") or 0),
                details=merged_details,
                error_message=work_error,
            )
            self.run_index_housekeeping()
            self._index_job_lock.release()

    def start_index_check(self, reason="manual"):
        if self._index_job_lock.locked():
            return {"started": False, "status": dict(self.index_status)}

        if reason != "watch":
            status = self.schedule_next_ingest_check()
            self._watch_reschedule.set()
        else:
            status = dict(self.index_status)

        thread = threading.Thread(
            target=self.check_for_training_changes,
            kwargs={"reason": reason},
            name=f"circuitshelf-index-{reason}",
            daemon=True,
        )
        thread.start()
        return {"started": True, "status": status}

    def ingest_watch_loop(self):
        self.schedule_next_ingest_check()
        self.trace_logger.info(f"👁️ Training watcher enabled. Checking every {self.ingest_watch_interval_seconds()} seconds.")

        while not self._watch_stop.is_set():
            remaining = self.seconds_until_next_ingest_check()
            if self._watch_stop.wait(remaining):
                break
            if self._watch_reschedule.is_set():
                self._watch_reschedule.clear()
                self.schedule_next_ingest_check()
                continue
            self.schedule_next_ingest_check()
            self.start_index_check("watch")

    def start_ingest_watcher(self):
        if not self.config.get("INGEST_WATCH_ENABLED", True):
            self.set_index_status(enabled=False)
            return
        if self._watch_thread and self._watch_thread.is_alive():
            return
        self._watch_stop.clear()
        self._watch_thread = threading.Thread(
            target=self.ingest_watch_loop,
            name="circuitshelf-ingest-watch",
            daemon=True,
        )
        self._watch_thread.start()

    def stop_ingest_watcher(self):
        self._watch_stop.set()

    def apply_ingest_watch_enabled(self, value):
        if value:
            self.set_index_status(enabled=True)
            self.start_ingest_watcher()
        else:
            self.stop_ingest_watcher()
            self.set_index_status(enabled=False, nextCheckAt=None)

    def apply_ingest_watch_interval(self, _value):
        self.schedule_next_ingest_check()
        self._watch_reschedule.set()

    def get_or_build_index(self):
        if not os.path.exists(self.training_dir):
            self.trace_logger.error(f"❌ Training folder '{self.training_dir}' not found! Cannot proceed.")
            raise SystemExit(1)

        self.trace_logger.info("🔄 Starting index load or build...")
        start_time = time.time()
        manifest = self.build_ingest_manifest()
        current_manifest = manifest.scan()
        previous_manifest = self.vector_store.load_document_records()

        if previous_manifest:
            try:
                chunks, sources, metadata, embeddings = self.vector_store.load_state_payload()
                self.state.set_chunks(chunks)
                self.state.set_sources(sources)
                self.state.set_metadata(metadata)
                self.state.set_embeddings(embeddings)
                self.state.set_index(None)
                image_count = self.load_db_image_state()

                if not chunks or not embeddings:
                    if self.vector_store.counts()["documents"] == 0 and self.vector_store.pending_review_count() > 0:
                        self.state.replace_catalog(
                            chunks=[],
                            sources=[],
                            metadata=[],
                            embeddings=[],
                            image_store={},
                            image_captions={},
                            image_page_text={},
                            image_mime_types={},
                            image_id_list=[],
                            index=None,
                        )
                        duration = time.time() - start_time
                        self.trace_logger.info(
                            "✅ DB has pending review documents but no approved catalog; "
                            f"serving empty active state in {duration:.2f} sec"
                        )
                        return
                    raise ValueError("DB vector catalog is incomplete.")

                changes = manifest.diff(previous_manifest, current_manifest)
                if not changes.has_changes:
                    image_counts = self.image_store.counts()
                    if image_counts["referenced"] > image_counts["stored"]:
                        self.trace_logger.warning(
                            "⚠️ DB image catalog is incomplete; serving the existing text/vector catalog. "
                            "Run an index check to repair missing image rows."
                        )
                    if image_counts["stored"] > image_counts["embeddings"]:
                        backfilled = self.backfill_missing_image_embeddings()
                        if backfilled:
                            image_count = self.load_db_image_state()
                    duration = time.time() - start_time
                    self.system_log_build_info(
                        self.trace_logger,
                        chunks,
                        embeddings,
                        self.state.get_image_id_list(),
                        duration,
                    )
                    self.trace_logger.info(f"✅ DB catalog loaded in {duration:.2f} sec with {image_count} image entries")
                    return

                self.trace_logger.info(
                    f"🔁 Training changes detected at startup. Added: {len(changes.added)}, "
                    f"modified: {len(changes.modified)}, removed: {len(changes.removed)}, "
                    f"unchanged: {len(changes.unchanged)}. Serving the DB catalog; "
                    "watcher or manual Check now will ingest changes."
                )
                self.set_index_status(
                    lastReason="startup",
                    lastResult="training_changes_pending",
                    lastChanges=self.file_changes_payload(changes),
                )
                duration = time.time() - start_time
                self.system_log_build_info(
                    self.trace_logger,
                    chunks,
                    embeddings,
                    self.state.get_image_id_list(),
                    duration,
                )
                self.trace_logger.info(f"✅ DB catalog loaded in {duration:.2f} sec with pending training changes")
                return
            except Exception as exc:
                self.trace_logger.warning(f"🧹 DB catalog load failed, rebuilding from source documents: {exc}")

        self.state.replace_catalog(
            chunks=[],
            sources=[],
            metadata=[],
            embeddings=[],
            image_store={},
            image_captions={},
            image_page_text={},
            image_mime_types={},
            image_id_list=[],
            index=None,
        )
        if current_manifest:
            self.set_index_status(
                lastReason="startup",
                lastResult="source_documents_waiting",
                lastChanges={
                    "added": len(current_manifest),
                    "modified": 0,
                    "removed": 0,
                    "unchanged": 0,
                    "addedFiles": list(current_manifest.keys())[:20],
                    "modifiedFiles": [],
                    "removedFiles": [],
                },
            )
        duration = time.time() - start_time
        self.trace_logger.info(
            "✅ DB catalog is empty; serving empty state. "
            f"{len(current_manifest)} source files are waiting for upload/manual indexing. "
            f"Startup completed in {duration:.2f} sec"
        )
