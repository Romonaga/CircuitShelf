"""OCR helpers for ingestion and auditability."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean
from typing import Any

import pytesseract
from PIL import Image, ImageStat
from pytesseract import Output


@dataclass(frozen=True)
class OcrResult:
    text: str
    confidence: float | None
    skipped: bool = False
    skip_reason: str = ""


def should_skip_image(image: Image.Image, config: dict[str, Any]) -> tuple[bool, str]:
    width, height = image.size
    min_width = int(config.get("OCR_MIN_IMAGE_WIDTH", 20))
    min_height = int(config.get("OCR_MIN_IMAGE_HEIGHT", 20))
    min_area = int(config.get("OCR_MIN_IMAGE_AREA", 900))
    min_contrast = float(config.get("OCR_MIN_IMAGE_CONTRAST", 0.0))

    if width < min_width or height < min_height:
        return True, f"image too small ({width}x{height})"
    if width * height < min_area:
        return True, f"image area too small ({width * height})"

    if min_contrast > 0:
        grayscale = image.convert("L")
        contrast = ImageStat.Stat(grayscale).stddev[0]
        if contrast < min_contrast:
            return True, f"image contrast too low ({contrast:.2f})"

    return False, ""


def run_ocr(image: Image.Image, config: dict[str, Any]) -> OcrResult:
    skip, reason = should_skip_image(image, config)
    if skip:
        return OcrResult(text="", confidence=None, skipped=True, skip_reason=reason)

    if config.get("OCR_USE_TESSERACT_CONFIDENCE", True):
        data = pytesseract.image_to_data(image, output_type=Output.DICT)
        words = []
        confidences = []

        for raw_text, raw_confidence in zip(data.get("text", []), data.get("conf", [])):
            word = str(raw_text).strip()
            if not word:
                continue
            words.append(word)
            try:
                confidence = float(raw_confidence)
            except (TypeError, ValueError):
                continue
            if confidence >= 0:
                confidences.append(confidence)

        text = " ".join(words).strip()
        avg_confidence = fmean(confidences) if confidences else None
        return OcrResult(text=text, confidence=avg_confidence)

    text = pytesseract.image_to_string(image).strip()
    return OcrResult(text=text, confidence=None)
