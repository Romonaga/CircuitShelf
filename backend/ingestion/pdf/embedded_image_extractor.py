from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import fitz

from ocr_utils import should_skip_image_dimensions


@dataclass(frozen=True)
class EmbeddedPdfImage:
    order: int
    page_number: int
    image_key: str
    image_bytes: bytes
    width: int
    height: int


@dataclass(frozen=True)
class EmbeddedPdfImageExtraction:
    images: list[EmbeddedPdfImage]
    skipped_tiny: int = 0
    skipped_duplicates: int = 0
    failed: int = 0


class EmbeddedPdfImageExtractor:
    """Extract useful embedded PDF images before rendered-page fallback logic."""

    def __init__(self, *, config: Any, trace_logger=None):
        self.config = config
        self.trace_logger = trace_logger

    def extract(self, path: str) -> EmbeddedPdfImageExtraction:
        images: list[EmbeddedPdfImage] = []
        skipped_tiny = 0
        skipped_duplicates = 0
        failed = 0
        seen_xrefs: set[int] = set()
        base_name = os.path.basename(path)

        with fitz.open(path) as pdf:
            for page_index, page in enumerate(pdf):
                page_number = page_index + 1
                for image_index, image in enumerate(page.get_images(full=True)):
                    try:
                        xref = int(image[0])
                        if not page.get_image_rects(xref):
                            continue
                        if xref in seen_xrefs:
                            skipped_duplicates += 1
                            continue
                        seen_xrefs.add(xref)

                        width = int(image[2] or 0) if len(image) > 2 else 0
                        height = int(image[3] or 0) if len(image) > 3 else 0
                        should_queue, reason = self.should_queue_dimensions(width, height)
                        if not should_queue:
                            skipped_tiny += 1
                            self._debug_skip(base_name, page_number, reason)
                            continue

                        extracted = pdf.extract_image(xref)
                        image_bytes = extracted.get("image") or b""
                        width = int(extracted.get("width") or width)
                        height = int(extracted.get("height") or height)
                        should_queue, reason = self.should_queue_dimensions(width, height)
                        if not should_queue or not image_bytes:
                            skipped_tiny += 1
                            self._debug_skip(base_name, page_number, reason or "empty image bytes")
                            continue

                        image_key = f"{base_name}_page{page_number}_img{len(images) + 1}"
                        images.append(
                            EmbeddedPdfImage(
                                order=len(images),
                                page_number=page_number,
                                image_key=image_key,
                                image_bytes=image_bytes,
                                width=width,
                                height=height,
                            )
                        )
                    except Exception as exc:
                        failed += 1
                        if self.trace_logger:
                            self.trace_logger.warning(
                                f"Failed to extract embedded PDF image on page {page_number} from {base_name}: {exc}"
                            )

        if self.trace_logger and (images or skipped_tiny or skipped_duplicates or failed):
            self.trace_logger.info(
                f"PDF embedded image extraction for {base_name}: "
                f"{len(images)} queued, {skipped_tiny} tiny/invalid skipped, "
                f"{skipped_duplicates} duplicate xrefs skipped, {failed} failed."
            )
        return EmbeddedPdfImageExtraction(
            images=images,
            skipped_tiny=skipped_tiny,
            skipped_duplicates=skipped_duplicates,
            failed=failed,
        )

    def should_queue_dimensions(self, width: int, height: int) -> tuple[bool, str]:
        if width <= 0 or height <= 0:
            return True, ""
        skip, reason = should_skip_image_dimensions(width, height, self._embedded_image_config())
        return not skip, reason

    def _embedded_image_config(self) -> dict[str, Any]:
        config = dict(getattr(self.config, "config", self.config))
        config["OCR_MIN_IMAGE_WIDTH"] = max(
            int(config.get("OCR_MIN_IMAGE_WIDTH", 20) or 20),
            int(config.get("PDF_EMBEDDED_IMAGE_OCR_MIN_WIDTH", 80) or 80),
        )
        config["OCR_MIN_IMAGE_HEIGHT"] = max(
            int(config.get("OCR_MIN_IMAGE_HEIGHT", 20) or 20),
            int(config.get("PDF_EMBEDDED_IMAGE_OCR_MIN_HEIGHT", 80) or 80),
        )
        config["OCR_MIN_IMAGE_AREA"] = max(
            int(config.get("OCR_MIN_IMAGE_AREA", 900) or 900),
            int(config.get("PDF_EMBEDDED_IMAGE_OCR_MIN_AREA", 6400) or 6400),
        )
        return config

    def _debug_skip(self, base_name: str, page_number: int, reason: str) -> None:
        if self.trace_logger:
            self.trace_logger.debug(f"Skipping embedded PDF image on page {page_number} from {base_name}: {reason}")
