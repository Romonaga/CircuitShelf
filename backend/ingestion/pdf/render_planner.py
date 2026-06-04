from __future__ import annotations

import re

from backend.ingestion.pdf.models import PdfPageExtraction, PdfRenderRequest
from backend.ingestion.pdf_visuals import rendered_page_image_key, visual_keyword_hits


PIN_OR_DATASHEET_PATTERN = re.compile(
    r"\b(pin(?:out|s)?|terminal functions?|pin description|connection diagram|package|"
    r"block diagram|typical application|schematic|timing diagram|truth table)\b",
    re.IGNORECASE,
)


class PdfRenderPlanner:
    def __init__(self, *, config, trace_logger=None):
        self.config = config
        self.trace_logger = trace_logger

    def plan(self, path: str, pages: list[PdfPageExtraction]) -> list[PdfRenderRequest]:
        if not self.config.get("PDF_RENDER_VECTOR_PAGES", True):
            return []
        if not pages:
            return []

        native_min_chars = int(self.config.get("PDF_RENDER_NATIVE_TEXT_MIN_CHARS", 80) or 80)
        sparse_pages = [page for page in pages if page.native_char_count < native_min_chars]
        scanned_ratio = len(sparse_pages) / max(1, len(pages))

        requests: list[tuple[int, PdfRenderRequest]] = []
        for page in pages:
            render, reason, score = self._should_render_page(page, scanned_ratio=scanned_ratio, native_min_chars=native_min_chars)
            if not render:
                continue
            requests.append(
                (
                    score,
                    PdfRenderRequest(
                        order=len(requests),
                        page_number=page.page_number,
                        image_key=rendered_page_image_key(path, page.page_number),
                        reason=reason,
                    ),
                )
            )

        if scanned_ratio < 0.6:
            max_pages = int(self.config.get("PDF_RENDER_MAX_PAGES_PER_DOC", 8) or 0)
            if max_pages > 0:
                requests = sorted(requests, key=lambda item: (-item[0], item[1].page_number))[:max_pages]
        requests.sort(key=lambda item: item[1].page_number)
        return [request for _score, request in requests]

    def _should_render_page(self, page: PdfPageExtraction, *, scanned_ratio: float, native_min_chars: int) -> tuple[bool, str, int]:
        text = page.searchable_text
        sparse_native_text = page.native_char_count < native_min_chars
        render_raster_pages = bool(self.config.get("PDF_RENDER_RASTER_PAGES", True))
        min_raster_coverage = float(self.config.get("PDF_RENDER_MIN_RASTER_COVERAGE", 0.8) or 0.8)
        min_drawings = int(self.config.get("PDF_RENDER_MIN_DRAWINGS", 100) or 100)

        if scanned_ratio >= 0.6 and sparse_native_text:
            return True, "scanned page OCR", 10_000 - page.page_number
        if render_raster_pages and page.image_count > 0 and page.raster_coverage >= min_raster_coverage and sparse_native_text:
            return True, "raster-heavy page OCR", 8_000 + int(page.raster_coverage * 100)

        hits = visual_keyword_hits(text)
        has_datasheet_visual_text = bool(PIN_OR_DATASHEET_PATTERN.search(text))
        if page.drawing_count >= min_drawings * 2:
            return True, "dense vector page", 4_000 + page.drawing_count
        if page.drawing_count >= min_drawings and (hits or has_datasheet_visual_text):
            return True, "visual datasheet page", 3_000 + page.drawing_count + len(hits) * 50
        if has_datasheet_visual_text and page.image_count:
            return True, "datasheet figure page", 2_000 + page.image_count * 20
        return False, "", 0
