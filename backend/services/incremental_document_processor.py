from __future__ import annotations

import os
import time

import numpy as np

from backend.domain.statuses import DocumentStatusId
from backend.ingestion.ocr_engines import selected_ocr_mode
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
        build_document_intelligence,
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
        self.build_document_intelligence = build_document_intelligence
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
        start_details = {"documentPhase": "Starting"}
        try:
            start_details["fileSizeBytes"] = os.path.getsize(fpath)
        except OSError:
            pass
        active_count = self.begin_document_worker()
        try:
            self.update_index_progress(
                stage="processing_documents",
                current_file=source,
                file_details=start_details,
            )
            start = time.time()

            def detail_progress(**details):
                self.update_index_progress(stage="processing_documents", current_file=source, file_details=details)

            document = self.process_file_by_type(
                fpath,
                ingested_state,
                self.trace_logger,
                ingest_chunker,
                ingest_token_utils,
                progress_callback=detail_progress,
            )
            elapsed = time.time() - start
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
                "extractElapsedSeconds": elapsed,
                "activeDocumentWorkersAtStart": active_count,
                "fileSizeBytes": start_details.get("fileSizeBytes"),
                "ocrStats": getattr(document, "ocr_stats", {}) if document is not None else {},
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
        persist_started = time.time()

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
            status=DocumentStatusId.PENDING,
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
        intelligence = self._build_document_intelligence(source, ingested_state)
        self.mark_source_ready_for_review(source)
        ai_review = self.maybe_review_ingestion_with_openai(
            source,
            ingested_state,
            document_stats,
            intelligence=intelligence,
            progress_callback=lambda **details: self.update_index_progress(
                stage="processing_documents",
                current_file=source,
                file_details=details,
            ),
        )
        final_details = {
            **self.summarize_document_ingest_stats(document_stats),
            **image_result,
            **selected_ocr_mode(self.config),
            **(extracted.get("ocrStats") or {}),
            **self._intelligence_details(intelligence),
        }
        if ai_review:
            final_details["aiIngestionReviews"] = 1
            final_details["aiIngestionReviewPaidBy"] = ai_review.get("paidBy")
        self.update_index_progress(
            stage="processing_documents",
            finished_file=source,
            details={**final_details, "lastCompletedDocument": source},
        )
        persist_elapsed = time.time() - persist_started
        self.trace_logger.info(
            self._document_summary_line(
                source=source,
                extracted=extracted,
                build_result=build_result,
                details=final_details,
                persist_elapsed=persist_elapsed,
                ai_review=ai_review,
            )
        )
        return build_result, final_details

    def _build_document_intelligence(self, source: str, ingested_state) -> dict | None:
        if not self.build_document_intelligence:
            return None
        self.update_index_progress(
            current_file=source,
            file_details={"documentPhase": "Datasheet intelligence"},
        )
        try:
            intelligence = self.build_document_intelligence(source, ingested_state)
        except Exception as exc:
            self.trace_logger.warning(f"Datasheet intelligence unavailable for {source}: {exc}")
            return None
        if intelligence and intelligence.get("componentName"):
            pin_count = len((intelligence.get("pinout") or {}).get("pins") or [])
            fact_count = len(intelligence.get("facts") or [])
            self.trace_logger.info(
                f"🧩 Datasheet intelligence for {source}: "
                f"{intelligence.get('componentName')} ({intelligence.get('componentType') or 'component'}), "
                f"pins={pin_count}, facts={fact_count}, confidence={float(intelligence.get('confidence') or 0):.2f}."
            )
        return intelligence

    @staticmethod
    def _intelligence_details(intelligence: dict | None) -> dict:
        if not intelligence:
            return {}
        return {
            "detectedPins": len((intelligence.get("pinout") or {}).get("pins") or []),
            "facts": len(intelligence.get("facts") or []),
        }

    def mark_source_ready_for_review(self, source):
        ready_sources = self.vector_store.set_sources_status([source], DocumentStatusId.NEEDS_REVIEW)
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

    def _document_summary_line(self, *, source, extracted, build_result, details, persist_elapsed, ai_review):
        extract_elapsed = self._float_value(extracted.get("extractElapsedSeconds"))
        total_elapsed = extract_elapsed + persist_elapsed
        file_size = self._format_bytes(extracted.get("fileSizeBytes"))
        ai_part = "ai=none"
        if ai_review:
            cost = self._float_value(ai_review.get("estimatedCost"))
            provider = ai_review.get("provider") or "ai"
            paid_by = ai_review.get("paidBy") or "unknown"
            ai_part = f"ai={provider}/{paid_by} cost=${cost:.6f}"
        return (
            "✅ Document ingest complete: "
            f"{source} | status=needs_review | total={total_elapsed:.2f}s "
            f"extract={extract_elapsed:.2f}s save={persist_elapsed:.2f}s | "
            f"size={file_size} workers={self._int_value(extracted.get('activeDocumentWorkersAtStart'))} | "
            f"chunks={build_result.chunks}/{self._int_value(details.get('rawChunks'))} "
            f"dropped={build_result.dropped_chunks} | "
            f"images={self._int_value(details.get('storedImages'))}/{self._int_value(details.get('extractedImages'))} "
            f"ocr={self._int_value(details.get('ocrImageTexts'))} "
            f"indexed_image_text={self._int_value(details.get('indexedImageTexts'))} "
            f"ocr_engine={details.get('ocrEngineBreakdown') or details.get('ocrMode') or 'n/a'} "
            f"ocr_fallbacks={self._int_value(details.get('ocrFallbacks'))} | "
            f"ocr_fallback_reason={details.get('ocrFallbackErrors') or 'n/a'} | "
            f"{ai_part}"
        )

    @staticmethod
    def _int_value(value) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _float_value(value) -> float:
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0

    @classmethod
    def _format_bytes(cls, value) -> str:
        size = cls._float_value(value)
        if size <= 0:
            return "n/a"
        units = ("B", "KB", "MB", "GB")
        index = 0
        while size >= 1024 and index < len(units) - 1:
            size /= 1024
            index += 1
        return f"{size:.1f}{units[index]}"
