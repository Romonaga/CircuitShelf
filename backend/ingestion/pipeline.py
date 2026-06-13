from __future__ import annotations

import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from backend.ingestion.document_classifier import classify_document
from backend.ingestion.document_extractors import DocumentExtractor
from backend.ingestion.document_state_writer import DocumentStateWriter, ocr_section
from backend.ingestion.file_scanner import extract_first_number, scan_ingest_folder
from backend.ingestion.models import ExtractedDocument, ImageAsset
from backend.ingestion.worker_sizing import cpu_thermal_worker_pressure
from backend.services.resource_sensors import read_cpu_temperature_status


class IngestionPipeline:
    def __init__(
        self,
        *,
        config: Any,
        trace_logger,
        run_ocr,
        detected_cpu_count,
        reserved_core_count,
        usable_core_count,
        document_worker_count,
        ocr_worker_count,
        current_document_workers,
        local_gpu_ocr_slots,
        begin_document_worker,
        finish_document_worker,
        pdf_ext: str,
    ):
        self.config = config
        self.trace_logger = trace_logger
        self.run_ocr = run_ocr
        self.detected_cpu_count = detected_cpu_count
        self.reserved_core_count = reserved_core_count
        self.usable_core_count = usable_core_count
        self.document_worker_count = document_worker_count
        self.ocr_worker_count = ocr_worker_count
        self.current_document_workers = current_document_workers
        self.local_gpu_ocr_slots = local_gpu_ocr_slots
        self.begin_document_worker = begin_document_worker
        self.finish_document_worker = finish_document_worker
        self.pdf_ext = pdf_ext
        self.document_extractor = DocumentExtractor(
            config=config,
            trace_logger=trace_logger,
            run_ocr=run_ocr,
            ocr_worker_count=ocr_worker_count,
            current_document_workers=current_document_workers,
            local_gpu_ocr_slots=local_gpu_ocr_slots,
            detected_cpu_count=detected_cpu_count,
            reserved_core_count=reserved_core_count,
            pdf_ext=pdf_ext,
        )
        self.state_writer = DocumentStateWriter(config=config, trace_logger=trace_logger)

    def process_file_by_type(self, fpath, target_state, trace_logger, chunker, token_utils, progress_callback=None):
        document = self.document_extractor.extract_by_type(fpath, chunker, progress_callback)
        if document is None:
            return None

        self._apply_profile(document)
        if progress_callback:
            progress_callback(
                currentDocument=os.path.basename(fpath),
                documentPhase="Chunking extracted text",
                documentType=document.profile.document_type if document.profile else "unknown",
        )
        self._store_extracted_document(document, target_state, chunker, token_utils)
        return document

    def load_documents_parallel(
        self,
        folder,
        files_selected,
        clear_existing=True,
        target_state=None,
        target_chunker=None,
        target_token_utils=None,
        progress_callback=None,
    ):
        if target_state is None or target_chunker is None or target_token_utils is None:
            raise ValueError("target_state, target_chunker, and target_token_utils are required.")
        if clear_existing:
            target_state.clear_all()

        if isinstance(files_selected, list):
            file_list = list(files_selected)
        else:
            file_list = self._scan_folder(folder)
        file_list.sort(key=extract_first_number)

        if progress_callback:
            progress_callback(stage="processing_documents", total_files=len(file_list))
        if not file_list:
            self.trace_logger.warning(f"No supported documents found in {folder}.")
            return

        def process_file(filename):
            fpath = filename if os.path.isabs(filename) else os.path.join(folder, filename)
            active_count = self.begin_document_worker()
            try:
                if progress_callback:
                    progress_callback(stage="processing_documents", current_file=filename)
                thread_id = threading.get_ident()
                self.trace_logger.info(f"Thread-{thread_id} started for {filename} ({active_count} active document workers)")
                started = time.time()

                def detail_progress(**details):
                    if progress_callback:
                        progress_callback(stage="processing_documents", current_file=filename, file_details=details)

                self.process_file_by_type(
                    fpath,
                    target_state,
                    self.trace_logger,
                    target_chunker,
                    target_token_utils,
                    progress_callback=detail_progress,
                )
                self.trace_logger.info(f"Thread-{thread_id} finished {filename} in {time.time() - started:.2f}s")
            finally:
                if progress_callback:
                    progress_callback(stage="processing_documents", finished_file=filename)
                self.finish_document_worker()

        cpu_count = self.detected_cpu_count()
        cpu_temperature = read_cpu_temperature_status().get("temperatureC")
        configured_workers = self.document_worker_count(len(file_list), cpu_count=cpu_count)
        thermal_pressure = cpu_thermal_worker_pressure(configured_workers, cpu_temperature)
        max_workers = int(thermal_pressure["targetWorkers"])
        self.trace_logger.info(
            f"Ingest worker budget: {cpu_count} cores detected, reserving {self.reserved_core_count(cpu_count)}, "
            f"{self.usable_core_count(cpu_count)} usable, {max_workers} document workers for {len(file_list)} files."
        )
        if thermal_pressure.get("level") not in {"headroom", "unavailable", "not_applicable"}:
            self.trace_logger.warning(
                f"CPU thermal guard reduced document workers from {configured_workers} to {max_workers}: "
                f"{thermal_pressure.get('temperatureC')}C, {thermal_pressure.get('reason')}."
            )
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(process_file, filename): filename for filename in file_list}
            for future in as_completed(futures):
                future.result()

    def _scan_folder(self, folder: str) -> list[str]:
        return scan_ingest_folder(folder, config=self.config, pdf_ext=self.pdf_ext, trace_logger=self.trace_logger)

    def _extract_pdf(self, fpath: str, chunker, progress_callback=None):
        return self.document_extractor.extract_pdf(fpath, chunker, progress_callback)

    def _extract_docx(self, fpath: str, chunker):
        return self.document_extractor.extract_docx(fpath, chunker)

    def _extract_text(self, fpath: str):
        return self.document_extractor.extract_text(fpath)

    def _extract_image(self, fpath: str, chunker):
        return self.document_extractor.extract_image(fpath, chunker)

    def _apply_profile(self, document: ExtractedDocument) -> None:
        document.profile = classify_document(document.source_path, document.pages)
        profile = document.profile
        self.trace_logger.debug(
            f"Ingest profile for {os.path.basename(document.source_path)}: "
            f"{profile.document_type} ({profile.confidence:.2f})"
            + (f", component {profile.component_name}" if profile.component_name else "")
        )

    def _store_extracted_document(self, document: ExtractedDocument, target_state, chunker, token_utils) -> None:
        self.state_writer.store_extracted_document(document, target_state, chunker, token_utils)

    @staticmethod
    def _ocr_section(asset: ImageAsset) -> str:
        return ocr_section(asset)

    def _extract_docx_textbox_images(self, fpath: str, chunker) -> list[ImageAsset]:
        return self.document_extractor.extract_docx_textbox_images(fpath, chunker)

    @staticmethod
    def extract_page_number(value) -> int | None:
        match = re.search(r"_page(\d+)", str(value or ""))
        return int(match.group(1)) if match else None
