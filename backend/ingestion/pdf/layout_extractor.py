from __future__ import annotations

import os
import re
from typing import Callable

import pdfplumber

from backend.ingestion.pdf.models import PdfPageExtraction, PdfTable


ProgressCallback = Callable[..., None] | None


class PdfLayoutExtractor:
    """Extract text, tables, and lightweight layout signals without PyMuPDF."""

    def __init__(self, *, trace_logger=None):
        self.trace_logger = trace_logger

    def extract(self, path: str, progress_callback: ProgressCallback = None) -> list[PdfPageExtraction]:
        base_name = os.path.basename(path)
        pages: list[PdfPageExtraction] = []
        with pdfplumber.open(path) as pdf:
            total_pages = len(pdf.pages)
            for index, page in enumerate(pdf.pages):
                page_number = index + 1
                if progress_callback and _should_report_page(page_number, total_pages):
                    progress_callback(
                        currentDocument=base_name,
                        documentPhase="Extracting PDF text",
                        pdfPage=page_number,
                        pdfPages=total_pages,
                    )
                text = self._extract_text(page)
                tables = self._extract_tables(page_number, page)
                pages.append(
                    PdfPageExtraction(
                        page_number=page_number,
                        text=text,
                        tables=tables,
                        image_count=len(getattr(page, "images", []) or []),
                        drawing_count=self._drawing_count(page),
                        raster_coverage=self._raster_coverage(page),
                        width=float(page.width or 0),
                        height=float(page.height or 0),
                    )
                )
        return pages

    def _extract_text(self, page) -> str:
        try:
            text = page.extract_text(
                x_tolerance=1.5,
                y_tolerance=3,
                layout=True,
                keep_blank_chars=False,
            )
        except TypeError:
            text = page.extract_text(x_tolerance=1.5, y_tolerance=3)
        except Exception as exc:
            if self.trace_logger:
                self.trace_logger.warning(f"PDF text extraction failed on page {getattr(page, 'page_number', '?')}: {exc}")
            text = ""
        return _normalize_page_text(text or "")

    def _extract_tables(self, page_number: int, page) -> list[PdfTable]:
        raw_tables = self._extract_line_tables(page_number, page)
        if not raw_tables:
            raw_tables = self._extract_text_tables(page_number, page)

        tables: list[PdfTable] = []
        for raw in raw_tables or []:
            rows = [[_clean_cell(cell) for cell in row] for row in raw if row]
            rows = [row for row in rows if any(row)]
            if len(rows) >= 2:
                tables.append(PdfTable(page_number=page_number, rows=rows))
        return tables

    def _extract_line_tables(self, page_number: int, page) -> list:
        try:
            return page.extract_tables(
                table_settings={
                    "vertical_strategy": "lines",
                    "horizontal_strategy": "lines",
                    "snap_tolerance": 4,
                    "join_tolerance": 4,
                    "intersection_tolerance": 5,
                    "text_tolerance": 3,
                }
            )
        except Exception as exc:
            if self.trace_logger:
                self.trace_logger.debug(f"Line table extraction failed on page {page_number}: {exc}")
            return []

    def _extract_text_tables(self, page_number: int, page) -> list:
        try:
            return page.extract_tables(
                table_settings={
                    "vertical_strategy": "text",
                    "horizontal_strategy": "text",
                    "snap_tolerance": 3,
                    "join_tolerance": 3,
                    "text_tolerance": 3,
                    "min_words_vertical": 2,
                    "min_words_horizontal": 1,
                }
            )
        except Exception as exc:
            if self.trace_logger:
                self.trace_logger.debug(f"Text table extraction failed on page {page_number}: {exc}")
            return []

    @staticmethod
    def _drawing_count(page) -> int:
        return sum(len(getattr(page, name, []) or []) for name in ("lines", "rects", "curves"))

    @staticmethod
    def _raster_coverage(page) -> float:
        width = float(page.width or 0)
        height = float(page.height or 0)
        area = width * height
        if area <= 0:
            return 0.0
        covered = 0.0
        for image in getattr(page, "images", []) or []:
            image_width = float(image.get("width") or max(0.0, float(image.get("x1", 0)) - float(image.get("x0", 0))))
            image_height = float(image.get("height") or max(0.0, float(image.get("bottom", 0)) - float(image.get("top", 0))))
            covered += max(0.0, image_width) * max(0.0, image_height)
        return min(1.0, covered / area)


def _should_report_page(page_number: int, total_pages: int) -> bool:
    return page_number == 1 or page_number == total_pages or page_number % 25 == 0


def _clean_cell(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _normalize_page_text(text: str) -> str:
    lines = [re.sub(r"[ \t]+", " ", line).rstrip() for line in str(text or "").splitlines()]
    compacted = []
    blank = False
    for line in lines:
        if not line.strip():
            if not blank:
                compacted.append("")
            blank = True
            continue
        compacted.append(line.strip())
        blank = False
    return "\n".join(compacted).strip()
