from __future__ import annotations

import os
from io import BytesIO
from typing import Any

import fitz

from backend.ingestion.models import ExtractedDocument, ExtractedPage, ImageAsset
from backend.ingestion.pdf_native import mupdf_native_section
from ocr_utils import should_skip_image_dimensions
from pdf_visuals import page_image_coverage, rendered_page_image_key, should_render_visual_page


class PdfExtractor:
    def __init__(self, *, config: Any, ocr_assets, trace_logger=None):
        self.config = config
        self.ocr_assets = ocr_assets
        self.trace_logger = trace_logger

    def extract(self, path: str, progress_callback=None) -> ExtractedDocument:
        base_name = os.path.basename(path)
        pages: list[ExtractedPage] = []
        image_jobs: list[tuple] = []
        render_jobs: list[tuple] = []
        seen_xrefs: set[int] = set()
        skipped_images = 0
        duplicate_xrefs = 0

        if progress_callback:
            progress_callback(currentDocument=base_name, documentPhase="Scanning PDF")

        with mupdf_native_section():
            with fitz.open(path) as pdf:
                total_pages = len(pdf)
                for page_index, page in enumerate(pdf):
                    page_number = page_index + 1
                    if progress_callback and self._should_report_page(page_number, total_pages):
                        progress_callback(
                            currentDocument=base_name,
                            documentPhase="Scanning PDF",
                            pdfPage=page_number,
                            pdfPages=total_pages,
                            imageCandidates=len(image_jobs),
                            duplicateImageCandidates=duplicate_xrefs,
                            skippedImageCandidates=skipped_images,
                        )

                    text = (page.get_text("text") or "").strip()
                    pages.append(ExtractedPage(page_number=page_number, text=text))
                    page_image_refs = self._unique_page_images(page)

                    for image_number, image in enumerate(page_image_refs, start=1):
                        xref = int(image[0])
                        if xref in seen_xrefs:
                            duplicate_xrefs += 1
                            continue
                        seen_xrefs.add(xref)
                        width = int(image[2] or 0) if len(image) > 3 else 0
                        height = int(image[3] or 0) if len(image) > 3 else 0
                        if self._skip_dimensions(width, height):
                            skipped_images += 1
                            continue
                        try:
                            extracted = pdf.extract_image(xref)
                        except Exception as exc:
                            if self.trace_logger:
                                self.trace_logger.warning(f"Failed to extract PDF image xref {xref} on page {page_number}: {exc}")
                            continue
                        base_width = int(extracted.get("width") or width)
                        base_height = int(extracted.get("height") or height)
                        if self._skip_dimensions(base_width, base_height):
                            skipped_images += 1
                            continue
                        image_key = f"{base_name}_page{page_number}_img{image_number}"
                        image_jobs.append((len(image_jobs), page_number, extracted["image"], image_key, "embedded"))

                    if self._should_render_page(page, text, len(page_image_refs)):
                        try:
                            render_jobs.append((len(image_jobs) + len(render_jobs), page_number, self._render_page_png(page), rendered_page_image_key(path, page_number), "rendered"))
                        except Exception as exc:
                            if self.trace_logger:
                                self.trace_logger.warning(f"Could not render PDF page {page_number} from {base_name}: {exc}")

        if progress_callback:
            progress_callback(
                currentDocument=base_name,
                documentPhase="OCR images",
                imageCandidates=len(image_jobs) + len(render_jobs),
                skippedImageCandidates=skipped_images,
                duplicateImageCandidates=duplicate_xrefs,
            )
        if self.trace_logger and (skipped_images or duplicate_xrefs):
            self.trace_logger.info(
                f"PDF image prefilter for {base_name}: {len(image_jobs)} embedded queued, "
                f"{len(render_jobs)} rendered pages, {skipped_images} tiny/invalid skipped, "
                f"{duplicate_xrefs} duplicate xrefs skipped."
            )

        page_text_by_number = {page.page_number: page.text for page in pages}
        assets = [
            self._asset_from_ocr_result(result, base_name, page_text_by_number)
            for result in self.ocr_assets.run_jobs(image_jobs + render_jobs)
        ]
        return ExtractedDocument(source_path=path, pages=pages, assets=assets)

    @staticmethod
    def _unique_page_images(page) -> list:
        seen = set()
        unique = []
        for image in page.get_images(full=True):
            xref = int(image[0])
            if xref in seen:
                continue
            seen.add(xref)
            unique.append(image)
        return unique

    @staticmethod
    def _should_report_page(page_number: int, total_pages: int) -> bool:
        return page_number == 1 or page_number == total_pages or page_number % 25 == 0

    def _skip_dimensions(self, width: int, height: int) -> bool:
        if width <= 0 or height <= 0:
            return False
        config = dict(getattr(self.config, "config", self.config))
        config["OCR_MIN_IMAGE_WIDTH"] = max(int(config.get("OCR_MIN_IMAGE_WIDTH", 20) or 20), int(config.get("PDF_EMBEDDED_IMAGE_OCR_MIN_WIDTH", 80) or 80))
        config["OCR_MIN_IMAGE_HEIGHT"] = max(int(config.get("OCR_MIN_IMAGE_HEIGHT", 20) or 20), int(config.get("PDF_EMBEDDED_IMAGE_OCR_MIN_HEIGHT", 80) or 80))
        config["OCR_MIN_IMAGE_AREA"] = max(int(config.get("OCR_MIN_IMAGE_AREA", 900) or 900), int(config.get("PDF_EMBEDDED_IMAGE_OCR_MIN_AREA", 6400) or 6400))
        skip, _ = should_skip_image_dimensions(width, height, config)
        return bool(skip)

    def _should_render_page(self, page, text: str, unique_image_count: int) -> bool:
        if not self.config.get("PDF_RENDER_VECTOR_PAGES", True):
            return False
        drawing_count = len(page.get_drawings())
        raster_coverage = page_image_coverage(page) if unique_image_count else 0.0
        sparse_native_text = len((text or "").strip()) < int(self.config.get("PDF_RENDER_NATIVE_TEXT_MIN_CHARS", 80) or 80)
        render, _hits = should_render_visual_page(
            text=text,
            drawing_count=drawing_count,
            image_count=unique_image_count,
            min_drawings=int(self.config.get("PDF_RENDER_MIN_DRAWINGS", 100) or 100),
            raster_coverage=raster_coverage,
            render_raster_pages=bool(self.config.get("PDF_RENDER_RASTER_PAGES", True)),
            min_raster_coverage=float(self.config.get("PDF_RENDER_MIN_RASTER_COVERAGE", 0.8) or 0.8),
            sparse_native_text=sparse_native_text,
        )
        return render

    def _render_page_png(self, page) -> bytes:
        zoom = float(self.config.get("PDF_RENDER_ZOOM", 1.5) or 1.5)
        pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        output = BytesIO()
        output.write(pixmap.tobytes("png"))
        return output.getvalue()

    @staticmethod
    def _asset_from_ocr_result(result: dict, base_name: str, page_text_by_number: dict[int, str]) -> ImageAsset:
        ocr_result = result["ocr_result"]
        page_number = result["page_number"]
        source_kind = result["source_kind"]
        image_key = result["image_key"]
        caption = (
            f"Rendered page {page_number} from {base_name}"
            if source_kind == "rendered"
            else f"Image from {base_name}, page {page_number}"
        )
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
