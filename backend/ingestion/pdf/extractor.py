from __future__ import annotations

import os
from typing import Any

from backend.ingestion.models import ExtractedDocument, ExtractedPage, ImageAsset
from backend.ingestion.pdf.embedded_image_extractor import EmbeddedPdfImageExtractor
from backend.ingestion.pdf.layout_extractor import PdfLayoutExtractor
from backend.ingestion.pdf.page_renderer import PdfiumPageRenderer
from backend.ingestion.pdf.render_planner import PdfRenderPlanner


class PdfDocumentExtractor:
    """First-class PDF extractor used by the active ingestion pipeline."""

    def __init__(self, *, config: Any, ocr_assets, trace_logger=None):
        self.config = config
        self.ocr_assets = ocr_assets
        self.trace_logger = trace_logger

    def extract(self, path: str, progress_callback=None) -> ExtractedDocument:
        base_name = os.path.basename(path)
        if progress_callback:
            progress_callback(currentDocument=base_name, documentPhase="Extracting PDF text")

        layout_pages = PdfLayoutExtractor(trace_logger=self.trace_logger).extract(path, progress_callback=progress_callback)
        pages = [
            ExtractedPage(page_number=page.page_number, text=page.searchable_text)
            for page in layout_pages
        ]

        render_requests = PdfRenderPlanner(config=self.config, trace_logger=self.trace_logger).plan(path, layout_pages)
        embedded_images = EmbeddedPdfImageExtractor(config=self.config, trace_logger=self.trace_logger).extract(path)
        if progress_callback:
            progress_callback(
                currentDocument=base_name,
                documentPhase="Rendering visual pages",
                pdfPages=len(layout_pages),
                imageCandidates=len(render_requests) + len(embedded_images.images),
                skippedImageCandidates=embedded_images.skipped_tiny,
                duplicateImageCandidates=embedded_images.skipped_duplicates,
            )

        rendered = PdfiumPageRenderer(
            scale=float(self.config.get("PDF_RENDER_ZOOM", 1.5) or 1.5),
            trace_logger=self.trace_logger,
        ).render_pages(path, [request.page_number for request in render_requests])

        page_text_by_number = {page.page_number: page.text for page in pages}
        image_jobs = [
            (image.order, image.page_number, image.image_bytes, image.image_key, "embedded")
            for image in embedded_images.images
        ]
        rendered_order_offset = len(image_jobs)
        for request in render_requests:
            image_bytes = rendered.get(request.page_number)
            if not image_bytes:
                continue
            image_jobs.append((rendered_order_offset + request.order, request.page_number, image_bytes, request.image_key, "rendered"))

        if progress_callback:
            progress_callback(
                currentDocument=base_name,
                documentPhase="OCR images",
                imageCandidates=len(image_jobs),
                skippedImageCandidates=0,
                duplicateImageCandidates=0,
            )
        if self.trace_logger:
            self.trace_logger.debug(
                f"PDF extraction for {base_name}: {len(layout_pages)} pages, "
                f"{sum(1 for page in layout_pages if page.tables)} pages with tables, "
                f"{len(embedded_images.images)} embedded images and {len(render_requests)} rendered pages queued for OCR."
            )

        ocr_results = self.ocr_assets.run_jobs(image_jobs)
        assets = [
            self._asset_from_ocr_result(result, base_name, page_text_by_number)
            for result in ocr_results
        ]
        return ExtractedDocument(source_path=path, pages=pages, assets=assets, ocr_stats=self._ocr_stats(ocr_results))

    @staticmethod
    def _ocr_stats(results: list[dict]) -> dict[str, int | str]:
        stats: dict[str, int | str] = {
            "ocrJobs": len(results),
            "ocrAccepted": 0,
            "ocrSkipped": 0,
            "ocrFailed": 0,
            "ocrTimedOut": 0,
            "ocrFallbacks": 0,
        }
        engines: dict[str, int] = {}
        fallback_errors: dict[str, int] = {}
        for result in results:
            ocr_result = result.get("ocr_result") or {}
            engine = str(ocr_result.get("engine") or "unknown")
            engines[engine] = engines.get(engine, 0) + 1
            if ocr_result.get("accepted"):
                stats["ocrAccepted"] = int(stats["ocrAccepted"]) + 1
            if ocr_result.get("skipped"):
                stats["ocrSkipped"] = int(stats["ocrSkipped"]) + 1
            if ocr_result.get("failed"):
                stats["ocrFailed"] = int(stats["ocrFailed"]) + 1
            if ocr_result.get("timedOut"):
                stats["ocrTimedOut"] = int(stats["ocrTimedOut"]) + 1
            if ocr_result.get("fallbackFrom"):
                stats["ocrFallbacks"] = int(stats["ocrFallbacks"]) + 1
                error = str(ocr_result.get("error") or "").strip()
                if error:
                    fallback_errors[error] = fallback_errors.get(error, 0) + 1
        stats["ocrEngineBreakdown"] = ", ".join(f"{name}:{count}" for name, count in sorted(engines.items()))
        if fallback_errors:
            stats["ocrFallbackErrors"] = "; ".join(
                f"{message[:160]} ({count})"
                for message, count in sorted(fallback_errors.items(), key=lambda item: item[1], reverse=True)[:3]
            )
        return stats

    @staticmethod
    def _asset_from_ocr_result(result: dict, base_name: str, page_text_by_number: dict[int, str]) -> ImageAsset:
        ocr_result = result["ocr_result"]
        page_number = result["page_number"]
        source_kind = result["source_kind"]
        image_key = result["image_key"]
        caption = f"Rendered page {page_number} from {base_name}" if source_kind == "rendered" else f"Image from {base_name}, page {page_number}"
        ocr_text = ocr_result["text"] if ocr_result["accepted"] else ""
        native_text = page_text_by_number.get(page_number, "") if source_kind == "rendered" else ""
        searchable_text = "\n".join(part for part in [caption, native_text, ocr_text] if part).strip()
        return ImageAsset(
            image_key=image_key,
            page_number=page_number,
            caption=caption,
            image_bytes=result["image_bytes"],
            searchable_text=searchable_text,
            ocr_text=ocr_text,
            ocr_score=float(ocr_result.get("score") or 0.0),
            ocr_confidence=ocr_result.get("confidence"),
            source_kind=source_kind,
        )
