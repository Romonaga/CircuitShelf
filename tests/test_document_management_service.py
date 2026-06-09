from pathlib import Path

from backend.services.document_management_service import DocumentManagementService


class FakeLogger:
    def __init__(self):
        self.infos = []
        self.warnings = []

    def info(self, message):
        self.infos.append(message)

    def warning(self, message):
        self.warnings.append(message)


class FakeVectorStore:
    def __init__(self, rows):
        self.rows = rows
        self.deleted = []

    def rel_path_for_source(self, source):
        return source

    def delete_document(self, source):
        self.deleted.append(source)
        return self.rows.pop(source, None)


def test_remove_document_deletes_db_row_source_file_and_empty_parent(tmp_path: Path):
    training_dir = tmp_path / "training"
    nested_dir = training_dir / "folder"
    nested_dir.mkdir(parents=True)
    source_file = nested_dir / "ne555.pdf"
    source_file.write_bytes(b"pdf")
    pruned = []
    service = DocumentManagementService(
        vector_store=FakeVectorStore({"folder/ne555.pdf": {"source_path": "folder/ne555.pdf", "deleted_ingest_scope_count": 1}}),
        training_dir=str(training_dir),
        trace_logger=FakeLogger(),
        prune_training_files_from_state=pruned.extend,
    )

    result, status = service.remove_document_from_store("folder/ne555.pdf")

    assert status == 200
    assert result["ok"] is True
    assert result["deletedFile"] is True
    assert not source_file.exists()
    assert not nested_dir.exists()
    assert pruned == ["folder/ne555.pdf"]


def test_remove_document_does_not_delete_outside_training_dir(tmp_path: Path):
    training_dir = tmp_path / "training"
    outside_file = tmp_path / "outside.pdf"
    training_dir.mkdir()
    outside_file.write_bytes(b"pdf")
    logger = FakeLogger()
    service = DocumentManagementService(
        vector_store=FakeVectorStore({"../outside.pdf": {"source_path": "../outside.pdf"}}),
        training_dir=str(training_dir),
        trace_logger=logger,
        prune_training_files_from_state=lambda _sources: None,
    )

    result, status = service.remove_document_from_store("../outside.pdf")

    assert status == 200
    assert result["deletedFile"] is False
    assert outside_file.exists()
    assert logger.warnings
