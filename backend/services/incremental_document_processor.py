from __future__ import annotations

import os
import threading
import time

import numpy as np

from backend.ingestion.index_builder import IndexBuilder


class IncrementalDocumentProcessor:
    def __init__(
        self,
        *,
        config,
        trace_logger,
        training_dir: str,
        vector_store,
        embedder,
        build_ingest_context,
        process_file_by_type,
        persist_db_image_state,
        maybe_review_ingestion_with_openai,
        collect_ingest_stats,
        count_ingest_chunks_by_document,
        count_ingest_images_by_document,
        summarize_document_ingest_stats,
        image_asset_belongs_to_document,
        begin_document_worker,
        finish_document_worker,
        update_index_progress,
        effective_embedding_batch_size,
    ):
        self.config = config
        self.trace_logger = trace_logger
        self.training_dir = training_dir
        self.vector_store = vector_store
        self.embedder = embedder
        self.build_ingest_context = build_ingest_context
        self.process_file_by_type = process_file_by_type
        self.persist_db_image_state = persist_db_image_state
        self.maybe_review_ingestion_with_openai = maybe_review_ingestion_with_openai
        self.collect_ingest_stats = collect_ingest_stats
        self.count_ingest_chunks_by_document = count_ingest_chunks_by_document
        self.count_ingest_images_by_document = count_ingest_images_by_document
        self.summarize_document_ingest_stats = summarize_document_ingest_stats
        self.image_asset_belongs_to_document = image_asset_belongs_to_document
        self.begin_document_worker = begin_document_worker
        self.finish_document_worker = finish_document_worker
        self.update_index_progress = update_index_progress
        self.effective_embedding_batch_size = effective_embedding_batch_size

    def extract_document(self, source):
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
            self.trace_logger.info(f"Thread-{thread_id} started for {source} ({active_count} active document workers)")
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
            self.trace_logger.info(f"Thread-{thread_id} extracted {source} in {elapsed:.2f}s")
            self.update_index_progress(
                stage="processing_documents",
                current_file=source,
                file_details={"documentPhase": "Extracted, waiting for DB save"},
            )
            return {
                "source": source,
                "state": ingested_state,
                "token_utils": ingest_token_utils,
                "chunker": ingest_chunker,
            }
        except Exception as exc:
            self.trace_logger.error(f"Error processing {source}: {exc}")
            raise
        finally:
            self.finish_document_worker()

    def persist_document(self, extracted, current_manifest):
        source = extracted["source"]
        ingested_state = extracted["state"]
        ingest_chunker = extracted["chunker"]

        raw_chunk_counts, raw_image_counts, raw_ocr_image_counts = self._raw_document_counts(ingested_state, source)
        self.update_index_progress(
            current_file=source,
            file_details={
                "documentPhase": "Embedding text",
                "rawChunks": sum(raw_chunk_counts.values()),
                "extractedImages": sum(raw_image_counts.values()),
                "ocrImageTexts": sum(raw_ocr_image_counts.values()),
            },
        )
        build_result = IndexBuilder(
            ingested_state,
            ingest_chunker,
            self.embedder,
            self.config,
            self.trace_logger,
            batch_size_resolver=self.effective_embedding_batch_size,
        ).build()
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
        self.trace_logger.info(f"{source} is ready for review.")
        return build_result, final_details

    def mark_source_ready_for_review(self, source):
        ready_sources = self.vector_store.set_sources_status([source], "needs_review")
        if source not in ready_sources:
            raise RuntimeError(f"{source} could not be marked ready for review.")
        return ready_sources

    def _raw_document_counts(self, ingested_state, source):
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
        return raw_chunk_counts, raw_image_counts, raw_ocr_image_counts
