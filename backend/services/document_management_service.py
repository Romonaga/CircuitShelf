import os
from typing import Callable


class DocumentManagementService:
    def __init__(
        self,
        *,
        vector_store,
        training_dir: str,
        trace_logger,
        prune_training_files_from_state: Callable[[list[str]], None],
    ):
        self.vector_store = vector_store
        self.training_dir = training_dir
        self.trace_logger = trace_logger
        self.prune_training_files_from_state = prune_training_files_from_state

    def remove_document_from_store(self, source: str, *, delete_file: bool = True) -> tuple[dict, int]:
        if not source:
            return {"error": "Document source is required."}, 400

        rel_source = self.vector_store.rel_path_for_source(source)
        row = self.vector_store.delete_document(rel_source)
        if not row:
            return {"error": "Document not found."}, 404
        self.prune_training_files_from_state([rel_source])
        deleted_file = self._delete_training_file(rel_source) if delete_file else False
        self.trace_logger.info(
            f"🧹 Removed document from store: {rel_source} | "
            f"deleted source file: {deleted_file} | "
            f"deleted ingest scope: {int(row.get('deleted_ingest_scope_count') or 0)}"
        )
        return {"ok": True, "document": dict(row), "deletedFile": deleted_file}, 200

    def _delete_training_file(self, rel_source: str) -> bool:
        target = self._safe_training_path(rel_source)
        if not target or not os.path.isfile(target):
            return False
        os.remove(target)
        self._prune_empty_parent_dirs(os.path.dirname(target))
        return True

    def _safe_training_path(self, rel_source: str) -> str | None:
        training_root = os.path.abspath(self.training_dir)
        target = os.path.abspath(os.path.join(training_root, rel_source))
        if target == training_root or not target.startswith(training_root + os.sep):
            self.trace_logger.warning(f"Blocked source file delete outside training folder: {rel_source}")
            return None
        return target

    def _prune_empty_parent_dirs(self, start_dir: str) -> None:
        training_root = os.path.abspath(self.training_dir)
        current = os.path.abspath(start_dir)
        while current.startswith(training_root + os.sep):
            try:
                os.rmdir(current)
            except OSError:
                return
            current = os.path.dirname(current)
