import os
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, as_completed, wait

import numpy as np

from index_builder import IndexBuildResult, IndexBuilder


class IncrementalIngestService:
    def __init__(
        self,
        *,
        config,
        trace_logger,
        training_dir: str,
        vector_store,
        embedder,
        build_ingest_manifest,
        build_ingest_context,
        process_file_by_type,
        load_documents_parallel,
        prune_training_files_from_state,
        persist_db_image_state,
        maybe_review_ingestion_with_openai,
        collect_ingest_stats,
        count_ingest_chunks_by_document,
        count_ingest_images_by_document,
        summarize_document_ingest_stats,
        image_asset_belongs_to_document,
        detected_cpu_count,
        reserved_core_count,
        usable_core_count,
        document_worker_count,
        persist_worker_count,
        begin_document_worker,
        finish_document_worker,
        update_index_progress,
        update_index_detail,
        index_status,
        effective_embedding_batch_size,
    ):
        self.config = config
        self.trace_logger = trace_logger
        self.training_dir = training_dir
        self.vector_store = vector_store
        self.embedder = embedder
        self.build_ingest_manifest = build_ingest_manifest
        self.build_ingest_context = build_ingest_context
        self.process_file_by_type = process_file_by_type
        self.load_documents_parallel = load_documents_parallel
        self.prune_training_files_from_state = prune_training_files_from_state
        self.persist_db_image_state = persist_db_image_state
        self.maybe_review_ingestion_with_openai = maybe_review_ingestion_with_openai
        self.collect_ingest_stats = collect_ingest_stats
        self.count_ingest_chunks_by_document = count_ingest_chunks_by_document
        self.count_ingest_images_by_document = count_ingest_images_by_document
        self.summarize_document_ingest_stats = summarize_document_ingest_stats
        self.image_asset_belongs_to_document = image_asset_belongs_to_document
        self.detected_cpu_count = detected_cpu_count
        self.reserved_core_count = reserved_core_count
        self.usable_core_count = usable_core_count
        self.document_worker_count = document_worker_count
        self.persist_worker_count = persist_worker_count
        self.begin_document_worker = begin_document_worker
        self.finish_document_worker = finish_document_worker
        self.update_index_progress = update_index_progress
        self.update_index_detail = update_index_detail
        self.index_status = index_status
        self.effective_embedding_batch_size = effective_embedding_batch_size

    def extract_document_for_incremental_ingest(self, source):
        ingested_state, ingest_token_utils, ingest_chunker = self.build_ingest_context()
        fpath = source if os.path.isabs(source) else os.path.join(self.training_dir, source)
        active_count = self.begin_document_worker()
        try:
            self.update_index_progress(
                stage="processing_documents",
                current_file=source,
                file_details={"documentPhase": "Starting"},
            )
            thread_id = threading.get_ident()
            self.trace_logger.info(f"🛠️ Thread-{thread_id} started for {source} ({active_count} active document workers)")
            start = time.time()

            def detail_progress(**details):
                self.update_index_progress(stage="processing_documents", current_file=source, file_details=details)

            self.process_file_by_type(
                fpath,
                ingested_state,
                self.trace_logger,
                ingest_chunker,
                ingest_token_utils,
                progress_callback=detail_progress,
            )
            if self.config.get("ENABLE_TOKEN_NORMALIZATION", False):
                ingest_token_utils.normalize_token_distribution()

            elapsed = time.time() - start
            self.trace_logger.info(f"✅ Thread-{thread_id} extracted {source} in {elapsed:.2f}s")
            self.update_index_progress(
                stage="processing_documents",
                current_file=source,
                file_details={"documentPhase": "Waiting to save"},
            )
            return {
                "source": source,
                "state": ingested_state,
                "token_utils": ingest_token_utils,
                "chunker": ingest_chunker,
            }
        except Exception as exc:
            self.trace_logger.error(f"❌ Error processing {source}: {exc}")
            raise
        finally:
            self.finish_document_worker()

    def persist_incremental_document(self, extracted, current_manifest):
        source = extracted["source"]
        ingested_state = extracted["state"]
        ingest_chunker = extracted["chunker"]

        raw_chunk_counts = self.count_ingest_chunks_by_document(ingested_state, vector_store=self.vector_store)
        raw_image_counts = self.count_ingest_images_by_document(
            ingested_state.get_image_store().keys(),
            [source],
            image_asset_belongs_to_document=self.image_asset_belongs_to_document,
        )
        raw_ocr_image_counts = self.count_ingest_images_by_document(
            ingested_state.get_image_page_text().keys(),
            [source],
            image_asset_belongs_to_document=self.image_asset_belongs_to_document,
        )
        self.update_index_progress(
            current_file=source,
            file_details={
                "documentPhase": "Embedding text",
                "rawChunks": sum(raw_chunk_counts.values()),
                "extractedImages": sum(raw_image_counts.values()),
                "ocrImageTexts": sum(raw_ocr_image_counts.values()),
            },
        )
        builder = IndexBuilder(
            ingested_state,
            ingest_chunker,
            self.embedder,
            self.config,
            self.trace_logger,
            batch_size_resolver=self.effective_embedding_batch_size,
        )
        build_result = builder.build()
        self.update_index_progress(
            current_file=source,
            file_details={
                "documentPhase": "Saving text chunks",
                "chunks": build_result.chunks,
                "droppedChunks": build_result.dropped_chunks,
                "indexedImageTexts": build_result.images,
            },
        )
        document_stats = self.collect_ingest_stats(
            ingested_state,
            [source],
            vector_store=self.vector_store,
            image_asset_belongs_to_document=self.image_asset_belongs_to_document,
            raw_chunk_counts=raw_chunk_counts,
            raw_image_counts=raw_image_counts,
            raw_ocr_image_counts=raw_ocr_image_counts,
        )
        self.vector_store.replace_sources(
            delete_rel_paths=[source],
            file_records=current_manifest,
            chunks=ingested_state.get_chunks(),
            sources=ingested_state.get_sources(),
            metadata=ingested_state.get_metadata(),
            embeddings=np.asarray(ingested_state.get_embeddings(), dtype="float32"),
            status="pending",
            document_stats=document_stats,
        )
        self.update_index_progress(
            current_file=source,
            file_details={
                "documentPhase": "Saving images",
                "extractedImages": sum(raw_image_counts.values()),
                "indexedImageTexts": build_result.images,
            },
        )
        image_result = self.persist_db_image_state(
            current_manifest,
            target_state=ingested_state,
            rel_paths=[source],
            progress_file=source,
        )
        self.mark_source_ready_for_review(source)
        ai_review = self.maybe_review_ingestion_with_openai(source, ingested_state, document_stats)
        final_details = {
            **self.summarize_document_ingest_stats(document_stats),
            **image_result,
        }
        if ai_review:
            final_details["aiIngestionReviews"] = 1
            final_details["aiIngestionReviewPaidBy"] = ai_review.get("paidBy")
        self.update_index_progress(
            stage="processing_documents",
            finished_file=source,
            details={**final_details, "lastCompletedDocument": source},
        )
        self.trace_logger.info(f"✅ {source} is ready for review.")
        return build_result, final_details

    def mark_source_ready_for_review(self, source):
        ready_sources = self.vector_store.set_sources_status([source], "needs_review")
        if source not in ready_sources:
            raise RuntimeError(f"{source} could not be marked ready for review.")
        return ready_sources

    def run_incremental_ingest(self, changes, current_manifest):
        if changes.removed:
            self.trace_logger.info(
                f"📚 Ignoring {len(changes.removed)} missing training files because the DB catalog is authoritative. "
                "Use Admin Remove to delete documents from CircuitShelf."
            )
        delete_rel_paths = changes.modified
        changed_rel_paths = changes.changed_or_added

        self.trace_logger.info(
            f"🔁 Incremental ingest. Added: {len(changes.added)}, modified: {len(changes.modified)}, "
            f"removed: {len(changes.removed)}"
        )
        self.prune_training_files_from_state(delete_rel_paths)

        total_chunks = 0
        total_dropped_chunks = 0
        total_images = 0
        embedding_dim = 0
        failed_files = []
        aggregate_details = {
            "rawChunks": 0,
            "chunks": 0,
            "droppedChunks": 0,
            "extractedImages": 0,
            "indexedImageTexts": 0,
            "ocrImageTexts": 0,
            "storedImages": 0,
            "skippedImages": 0,
        }
        final_details = {}
        if changed_rel_paths:
            cpu_count = self.detected_cpu_count()
            max_workers = self.document_worker_count(len(changed_rel_paths), cpu_count=cpu_count)
            save_workers = self.persist_worker_count(len(changed_rel_paths), cpu_count=cpu_count)
            self.trace_logger.info(
                f"⚙️ Ingest worker budget: {cpu_count} cores detected, reserving {self.reserved_core_count(cpu_count)}, "
                f"{self.usable_core_count(cpu_count)} usable, {max_workers} document workers and "
                f"{save_workers} save workers for {len(changed_rel_paths)} files."
            )
            self.update_index_progress(
                stage="processing_documents",
                total_files=len(changed_rel_paths),
                details={
                    "documents": len(changed_rel_paths),
                    "activeWorkers": max_workers,
                    "persistWorkers": save_workers,
                    "queuedSaveDocuments": 0,
                },
            )

            completed_documents = 0
            pending_persists = {}

            def update_aggregate_details(document_source, persist_future):
                nonlocal total_chunks, total_dropped_chunks, total_images, embedding_dim, final_details, completed_documents
                try:
                    build_result, document_details = persist_future.result()
                    total_chunks += build_result.chunks
                    total_dropped_chunks += build_result.dropped_chunks
                    total_images += build_result.images
                    embedding_dim = build_result.embedding_dim
                    completed_documents += 1
                    for key in aggregate_details:
                        aggregate_details[key] += int(document_details.get(key, 0) or 0)
                    final_details = {
                        "documents": len(changed_rel_paths),
                        "completedDocuments": completed_documents,
                        "persistWorkers": save_workers,
                        "queuedSaveDocuments": len(pending_persists),
                        **aggregate_details,
                        "failedDocuments": len(failed_files),
                    }
                    self.update_index_detail(**final_details)
                except ValueError as exc:
                    failed_files.append(document_source)
                    self.trace_logger.warning(f"⚠️ {document_source} produced no valid chunks: {exc}")
                    self.vector_store.delete_sources([document_source])
                    self.update_index_progress(
                        stage="processing_documents",
                        finished_file=document_source,
                        details={
                            "documents": len(changed_rel_paths),
                            "persistWorkers": save_workers,
                            "queuedSaveDocuments": len(pending_persists),
                            "failedDocuments": len(failed_files),
                            "failedFiles": failed_files[:10],
                        },
                    )
                except Exception as exc:
                    failed_files.append(document_source)
                    self.trace_logger.error(f"❌ Incremental document ingest failed for {document_source}: {exc}")
                    self.update_index_progress(
                        stage="processing_documents",
                        finished_file=document_source,
                        details={
                            "documents": len(changed_rel_paths),
                            "persistWorkers": save_workers,
                            "queuedSaveDocuments": len(pending_persists),
                            "failedDocuments": len(failed_files),
                            "failedFiles": failed_files[:10],
                        },
                    )

            def drain_persist_queue(*, block: bool):
                if not pending_persists:
                    return
                done, _ = wait(
                    pending_persists,
                    timeout=None if block else 0,
                    return_when=FIRST_COMPLETED,
                )
                for persist_future in done:
                    document_source = pending_persists.pop(persist_future)
                    update_aggregate_details(document_source, persist_future)

            with ThreadPoolExecutor(max_workers=max_workers) as extract_executor, ThreadPoolExecutor(max_workers=save_workers) as persist_executor:
                extract_futures = {
                    extract_executor.submit(self.extract_document_for_incremental_ingest, source): source
                    for source in changed_rel_paths
                }
                for future in as_completed(extract_futures):
                    source = extract_futures[future]
                    try:
                        extracted = future.result()
                        self.update_index_progress(
                            stage="processing_documents",
                            current_file=source,
                            file_details={"documentPhase": "Queued for save"},
                            details={
                                "persistWorkers": save_workers,
                                "queuedSaveDocuments": len(pending_persists) + 1,
                            },
                        )
                        persist_future = persist_executor.submit(self.persist_incremental_document, extracted, current_manifest)
                        pending_persists[persist_future] = source
                        while len(pending_persists) >= max(1, save_workers * 2):
                            drain_persist_queue(block=True)
                        drain_persist_queue(block=False)
                    except Exception as exc:
                        failed_files.append(source)
                        self.trace_logger.error(f"❌ Incremental document extract failed for {source}: {exc}")
                        self.update_index_progress(
                            stage="processing_documents",
                            finished_file=source,
                            details={
                                "documents": len(changed_rel_paths),
                                "persistWorkers": save_workers,
                                "queuedSaveDocuments": len(pending_persists),
                                "failedDocuments": len(failed_files),
                                "failedFiles": failed_files[:10],
                            },
                        )
                while pending_persists:
                    drain_persist_queue(block=True)

            final_details = {
                **final_details,
                "documents": len(changed_rel_paths),
                "completedDocuments": completed_documents,
                "persistWorkers": save_workers,
                "queuedSaveDocuments": 0,
                **aggregate_details,
                "failedDocuments": len(failed_files),
            }
        elif delete_rel_paths:
            self.vector_store.delete_sources(delete_rel_paths)

        build_result = None
        if total_chunks:
            build_result = IndexBuildResult(
                chunks=total_chunks,
                dropped_chunks=total_dropped_chunks,
                images=total_images,
                embedding_dim=embedding_dim,
            )
        return build_result, final_details

    def reindex_review_source(self, source):
        manifest = self.build_ingest_manifest()
        current_manifest = manifest.scan()
        if source not in current_manifest:
            raise FileNotFoundError(f"Training file not found: {source}")

        self.prune_training_files_from_state([source])
        ingested_state, ingest_token_utils, ingest_chunker = self.build_ingest_context()
        self.load_documents_parallel(
            folder=self.training_dir,
            files_selected=[source],
            clear_existing=True,
            target_state=ingested_state,
            target_chunker=ingest_chunker,
            target_token_utils=ingest_token_utils,
            progress_callback=self.update_index_progress,
        )
        raw_chunk_counts = self.count_ingest_chunks_by_document(ingested_state, vector_store=self.vector_store)
        raw_image_counts = self.count_ingest_images_by_document(
            ingested_state.get_image_store().keys(),
            [source],
            image_asset_belongs_to_document=self.image_asset_belongs_to_document,
        )
        raw_ocr_image_counts = self.count_ingest_images_by_document(
            ingested_state.get_image_page_text().keys(),
            [source],
            image_asset_belongs_to_document=self.image_asset_belongs_to_document,
        )
        self.update_index_progress(
            stage="embedding_chunks",
            details={
                "documents": 1,
                "rawChunks": sum(raw_chunk_counts.values()),
                "extractedImages": sum(raw_image_counts.values()),
                "ocrImageTexts": sum(raw_ocr_image_counts.values()),
            },
        )
        builder = IndexBuilder(
            ingested_state,
            ingest_chunker,
            self.embedder,
            self.config,
            self.trace_logger,
            batch_size_resolver=self.effective_embedding_batch_size,
        )
        build_result = builder.build()
        self.update_index_progress(
            stage="persisting_chunks",
            details={
                "documents": 1,
                "chunks": build_result.chunks,
                "droppedChunks": build_result.dropped_chunks,
                "extractedImages": sum(raw_image_counts.values()),
                "indexedImageTexts": build_result.images,
                "ocrImageTexts": sum(raw_ocr_image_counts.values()),
            },
        )
        document_stats = self.collect_ingest_stats(
            ingested_state,
            [source],
            vector_store=self.vector_store,
            image_asset_belongs_to_document=self.image_asset_belongs_to_document,
            raw_chunk_counts=raw_chunk_counts,
            raw_image_counts=raw_image_counts,
            raw_ocr_image_counts=raw_ocr_image_counts,
        )
        self.vector_store.replace_sources(
            delete_rel_paths=[source],
            file_records=current_manifest,
            chunks=ingested_state.get_chunks(),
            sources=ingested_state.get_sources(),
            metadata=ingested_state.get_metadata(),
            embeddings=np.asarray(ingested_state.get_embeddings(), dtype="float32"),
            status="pending",
            document_stats=document_stats,
        )
        self.update_index_progress(
            stage="persisting_images",
            details={
                "documents": 1,
                "chunks": build_result.chunks,
                "droppedChunks": build_result.dropped_chunks,
                "extractedImages": sum(raw_image_counts.values()),
                "indexedImageTexts": build_result.images,
            },
        )
        image_result = self.persist_db_image_state(current_manifest, target_state=ingested_state, rel_paths=[source])
        self.update_index_progress(stage="readying_review", details={**self.summarize_document_ingest_stats(document_stats), **image_result})
        self.mark_source_ready_for_review(source)
        self.maybe_review_ingestion_with_openai(source, ingested_state, document_stats)
        return build_result
