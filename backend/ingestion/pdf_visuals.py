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

VISUAL_REFERENCE_PATTERN = re.compile(
    r"\b(?:fig(?:ure)?\.?\s*\d+[a-z]?|table\s*\d+[a-z]?|pinout|pin configuration|pin layout|"
    r"package dimensions?|schematic|diagram|graph|chart|timing diagram|layout)\b",
    re.IGNORECASE,
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


def visual_references(text: str) -> list[str]:
    seen = []
    for match in VISUAL_REFERENCE_PATTERN.finditer(text or ""):
        value = re.sub(r"\s+", " ", match.group(0)).strip()
        if value and value.lower() not in {item.lower() for item in seen}:
            seen.append(value)
    return seen


def rendered_page_image_key(source_path: str, page_number: int) -> str:
    return f"{os.path.basename(source_path)}_page{int(page_number)}_render"


def link_chunks_to_rendered_pages(
    chunks: list[str],
    metadata: list[dict],
    source_path: str,
    available_image_ids: Iterable[str],
) -> int:
    available = set(available_image_ids)
    linked = 0

    for chunk, meta in zip(chunks, metadata):
        if meta.get("source_image_id"):
            continue
        try:
            page_number = int(meta.get("page") or 0)
        except (TypeError, ValueError):
            continue
        if page_number <= 0:
            continue

        image_key = rendered_page_image_key(source_path, page_number)
        if image_key not in available:
            continue

        references = visual_references(
            "\n".join(
                [
                    str(meta.get("section") or ""),
                    str(meta.get("category") or ""),
                    chunk or "",
                ]
            )
        )
        if not references:
            continue

        meta["source_image_id"] = image_key
        meta["visual_references"] = references
        linked += 1

    return linked


def should_render_visual_page(
    *,
    text: str,
    drawing_count: int,
    image_count: int,
    min_drawings: int,
    raster_coverage: float = 0.0,
    render_raster_pages: bool = False,
    min_raster_coverage: float = 0.8,
    sparse_native_text: bool = False,
    keywords: Iterable[str] = VISUAL_PAGE_KEYWORDS,
) -> tuple[bool, list[str]]:
    hits = visual_keyword_hits(text, keywords)
    if drawing_count >= min_drawings and hits:
        return True, hits
    if drawing_count >= min_drawings * 2:
        return True, hits
    if render_raster_pages and image_count > 0 and raster_coverage >= min_raster_coverage and (hits or sparse_native_text):
        return True, hits
    return False, hits


def page_image_coverage(page: fitz.Page) -> float:
    area = page.rect.width * page.rect.height
    if area <= 0:
        return 0.0

    covered = 0.0
    seen_xrefs = set()
    for image in page.get_images(full=True):
        xref = image[0]
        if xref in seen_xrefs:
            continue
        seen_xrefs.add(xref)
        try:
            for rect in page.get_image_rects(xref):
                clipped = rect & page.rect
                covered += max(0.0, clipped.width) * max(0.0, clipped.height)
        except Exception:
            continue
    return min(1.0, covered / area)


def render_pdf_visual_pages(
    path: str,
    *,
    max_pages: int | None = 8,
    min_drawings: int = 100,
    zoom: float = 1.5,
    render_raster_pages: bool = False,
    min_raster_coverage: float = 0.8,
    keywords: Iterable[str] = VISUAL_PAGE_KEYWORDS,
) -> list[RenderedPdfPage]:
    base_name = os.path.basename(path)
    candidates = []
    with fitz.open(path) as pdf:
        for page_index, page in enumerate(pdf):
            page_number = page_index + 1
            text = page.get_text().strip()
            drawing_count = len(page.get_drawings())
            image_count = len(page.get_images(full=True))
            raster_coverage = page_image_coverage(page)
            render, hits = should_render_visual_page(
                text=text,
                drawing_count=drawing_count,
                image_count=image_count,
                min_drawings=min_drawings,
                raster_coverage=raster_coverage,
                render_raster_pages=render_raster_pages,
                min_raster_coverage=min_raster_coverage,
                sparse_native_text=len(text) < 80,
                keywords=keywords,
            )
            if not render:
                continue
            raster_score = int(raster_coverage * min_drawings) if render_raster_pages else 0
            score = drawing_count + raster_score + (len(hits) * min_drawings)
            candidates.append((score, page_number, page_index, text, drawing_count, raster_coverage, hits))

        selected = sorted(candidates, key=lambda item: (-item[0], item[1]))
        if max_pages and max_pages > 0:
            selected = selected[:max_pages]
        selected.sort(key=lambda item: item[1])

        rendered_pages = []
        matrix = fitz.Matrix(float(zoom), float(zoom))
        for _, page_number, page_index, text, drawing_count, raster_coverage, hits in selected:
            page = pdf[page_index]
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            output = BytesIO()
            output.write(pixmap.tobytes("png"))
            if hits:
                hit_summary = ", ".join(hits[:5])
            elif drawing_count:
                hit_summary = "dense vector drawing"
            else:
                hit_summary = f"raster page coverage {raster_coverage:.0%}"
            caption = f"Rendered page {page_number} from {base_name} ({hit_summary})"
            searchable_text = f"{caption}\n{text}".strip()
            image_key = rendered_page_image_key(path, page_number)
            rendered_pages.append(
                RenderedPdfPage(
                    image_key=image_key,
                    page_number=page_number,
                    caption=caption,
                    searchable_text=searchable_text,
                    image_bytes=output.getvalue(),
                )
            )

    return rendered_pages
