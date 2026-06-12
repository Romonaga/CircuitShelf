from backend.ingestion.manifest import FileChanges
from backend.services.incremental_ingest_service import IncrementalIngestService


class StubLogger:
    def __init__(self):
        self.infos = []

    def info(self, message):
        self.infos.append(message)

    def warning(self, message):
        pass

    def error(self, message):
        pass


class StubVectorStore:
    def __init__(self):
        self.deleted = []

    def delete_sources(self, sources):
        self.deleted.extend(sources)


def service_with_stubs(vector_store, logger):
    noop = lambda *args, **kwargs: None
    return IncrementalIngestService(
        config={},
        trace_logger=logger,
        training_dir="training",
        vector_store=vector_store,
        embedder=None,
        build_ingest_manifest=noop,
        build_ingest_context=noop,
        process_file_by_type=noop,
        load_documents_parallel=noop,
        prune_training_files_from_state=noop,
        persist_db_image_state=noop,
        maybe_review_ingestion_with_openai=noop,
        build_document_intelligence=noop,
        collect_ingest_stats=noop,
        count_ingest_chunks_by_document=noop,
        count_ingest_images_by_document=noop,
        summarize_document_ingest_stats=noop,
        image_asset_belongs_to_document=noop,
        detected_cpu_count=lambda: 1,
        reserved_core_count=lambda _cpu_count: 0,
        usable_core_count=lambda _cpu_count: 1,
        document_worker_count=lambda *_args, **_kwargs: 1,
        persist_worker_count=lambda *_args, **_kwargs: 1,
        begin_document_worker=noop,
        finish_document_worker=noop,
        update_index_progress=noop,
        update_index_detail=noop,
        index_status={},
        effective_embedding_batch_size=lambda: 1,
    )


def test_incremental_ingest_deletes_removed_generated_vendor_dependencies_only():
    vector_store = StubVectorStore()
    logger = StubLogger()
    service = service_with_stubs(vector_store, logger)
    changes = FileChanges(
        added=[],
        modified=[],
        removed=[
            "sample/STM32/Demo/Drivers/CMSIS/Include/core_cm3.h",
            "sample/STM32/Demo/Drivers/STM32F1xx_HAL_Driver/Inc/stm32f1xx_hal_gpio.h",
            "sample/removed-by-user.pdf",
        ],
        unchanged=[],
    )

    build_result, details = service.run_incremental_ingest(changes, current_manifest={})

    assert build_result is None
    assert vector_store.deleted == [
        "sample/STM32/Demo/Drivers/CMSIS/Include/core_cm3.h",
        "sample/STM32/Demo/Drivers/STM32F1xx_HAL_Driver/Inc/stm32f1xx_hal_gpio.h",
    ]
    assert details["removedIgnoredDependencyDocuments"] == 2
    assert any("Ignoring 1 missing training files" in message for message in logger.infos)
