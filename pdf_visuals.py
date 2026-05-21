"""Helpers for preserving vector-heavy PDF pages as searchable images."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from io import BytesIO
from typing import Iterable

import fitz


VISUAL_PAGE_KEYWORDS = (
    "pin",
    "pinout",
    "package",
    "dimension",
    "dimensions",
    "fig.",
    "figure",
    "graph",
    "chart",
    "schematic",
    "diagram",
    "circuit",
    "typical application",
    "timing",
)


@dataclass(frozen=True)
class RenderedPdfPage:
    image_key: str
    page_number: int
    caption: str
    searchable_text: str
    image_bytes: bytes


def visual_keyword_hits(text: str, keywords: Iterable[str] = VISUAL_PAGE_KEYWORDS) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).lower()
    return [keyword for keyword in keywords if keyword in normalized]


def should_render_visual_page(
    *,
    text: str,
    drawing_count: int,
    image_count: int,
    min_drawings: int,
    keywords: Iterable[str] = VISUAL_PAGE_KEYWORDS,
) -> tuple[bool, list[str]]:
    hits = visual_keyword_hits(text, keywords)
    if drawing_count >= min_drawings and hits:
        return True, hits
    if drawing_count >= min_drawings * 2:
        return True, hits
    return False, hits


def render_pdf_visual_pages(
    path: str,
    *,
    max_pages: int = 8,
    min_drawings: int = 100,
    zoom: float = 1.5,
    keywords: Iterable[str] = VISUAL_PAGE_KEYWORDS,
) -> list[RenderedPdfPage]:
    if max_pages <= 0:
        return []

    base_name = os.path.basename(path)
    candidates = []
    with fitz.open(path) as pdf:
        for page_index, page in enumerate(pdf):
            page_number = page_index + 1
            text = page.get_text().strip()
            drawing_count = len(page.get_drawings())
            image_count = len(page.get_images(full=True))
            render, hits = should_render_visual_page(
                text=text,
                drawing_count=drawing_count,
                image_count=image_count,
                min_drawings=min_drawings,
                keywords=keywords,
            )
            if not render:
                continue
            score = drawing_count + (len(hits) * min_drawings)
            candidates.append((score, page_number, page_index, text, drawing_count, hits))

        selected = sorted(candidates, key=lambda item: (-item[0], item[1]))[:max_pages]
        selected.sort(key=lambda item: item[1])

        rendered_pages = []
        matrix = fitz.Matrix(float(zoom), float(zoom))
        for _, page_number, page_index, text, drawing_count, hits in selected:
            page = pdf[page_index]
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            output = BytesIO()
            output.write(pixmap.tobytes("png"))
            hit_summary = ", ".join(hits[:5]) if hits else "dense vector drawing"
            caption = f"Rendered page {page_number} from {base_name} ({hit_summary})"
            searchable_text = f"{caption}\n{text}".strip()
            rendered_pages.append(
                RenderedPdfPage(
                    image_key=f"{base_name}_page{page_number}_render",
                    page_number=page_number,
                    caption=caption,
                    searchable_text=searchable_text,
                    image_bytes=output.getvalue(),
                )
            )

    return rendered_pages
