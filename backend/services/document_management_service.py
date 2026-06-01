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
        deleted_file = False
        if delete_file:
            target = os.path.abspath(os.path.join(self.training_dir, rel_source))
            training_root = os.path.abspath(self.training_dir)
            if target.startswith(training_root + os.sep) and os.path.exists(target):
                os.remove(target)
                deleted_file = True
        self.trace_logger.info(f"🧹 Removed document from store: {rel_source} | deleted source file: {deleted_file}")
        return {"ok": True, "document": dict(row), "deletedFile": deleted_file}, 200
