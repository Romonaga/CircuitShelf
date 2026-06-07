"""External PaddleOCR runner used by the optional OCR engine.

This module is intentionally self-contained so it can run inside a separate
virtual environment with PaddleOCR installed, without importing CircuitShelf's
main application dependencies.
"""

from __future__ import annotations

import argparse
import json
from statistics import fmean
from typing import Any

import numpy as np
from PIL import Image
from paddleocr import PaddleOCR


def main() -> int:
    parser = argparse.ArgumentParser(description="Run PaddleOCR for one image and emit JSON.")
    parser.add_argument("--image", required=True)
    parser.add_argument("--lang", default="en")
    parser.add_argument("--device", default="gpu")
    parser.add_argument("--engine", default="")
    args = parser.parse_args()

    kwargs: dict[str, Any] = {
        "lang": args.lang,
        "device": args.device,
        "use_doc_orientation_classify": False,
        "use_doc_unwarping": False,
        "use_textline_orientation": False,
    }
    if args.engine:
        kwargs["engine"] = args.engine

    try:
        ocr = PaddleOCR(**kwargs)
    except TypeError:
        ocr = PaddleOCR(lang=args.lang, use_gpu=args.device == "gpu", use_angle_cls=False)

    image = Image.open(args.image).convert("RGB")
    input_image = np.asarray(image)
    if hasattr(ocr, "predict"):
        raw_result = ocr.predict(input_image)
    else:
        raw_result = ocr.ocr(input_image, cls=True)

    text, confidence = _extract_text_and_confidence(raw_result)
    print(json.dumps({"text": text, "confidence": confidence}, ensure_ascii=True))
    return 0


def _extract_text_and_confidence(raw_result: Any) -> tuple[str, float | None]:
    texts: list[str] = []
    scores: list[float] = []
    for item in _iter_result_items(raw_result):
        _collect_text_scores(item, texts, scores)
    cleaned = " ".join(text.strip() for text in texts if str(text).strip()).strip()
    if not scores:
        return cleaned, None
    average = fmean(scores)
    return cleaned, average * 100 if max(scores) <= 1.0 else average


def _iter_result_items(raw_result: Any):
    if raw_result is None:
        return
    if isinstance(raw_result, dict):
        yield raw_result
        return
    if hasattr(raw_result, "json"):
        json_value = raw_result.json
        if callable(json_value):
            json_value = json_value()
        yield json_value
        return
    if isinstance(raw_result, (list, tuple)):
        for item in raw_result:
            yield from _iter_result_items(item)
        return
    yield raw_result


def _collect_text_scores(item: Any, texts: list[str], scores: list[float]) -> None:
    if item is None:
        return
    if isinstance(item, dict):
        payload = item.get("res", item)
        if payload is not item:
            _collect_text_scores(payload, texts, scores)
            return
        rec_texts = item.get("rec_texts") or item.get("texts")
        rec_scores = item.get("rec_scores") or item.get("scores")
        if isinstance(rec_texts, list):
            texts.extend(str(text) for text in rec_texts if text)
            if isinstance(rec_scores, list):
                scores.extend(score for score in (_safe_float(value) for value in rec_scores) if score is not None)
            return
        text = item.get("text") or item.get("transcription")
        if text:
            texts.append(str(text))
        score = _safe_float(item.get("score") or item.get("confidence"))
        if score is not None:
            scores.append(score)
        return
    if isinstance(item, (list, tuple)):
        if len(item) >= 2 and isinstance(item[1], (list, tuple)) and len(item[1]) >= 2:
            text = item[1][0]
            score = _safe_float(item[1][1])
            if text:
                texts.append(str(text))
            if score is not None:
                scores.append(score)
            return
        for child in item:
            _collect_text_scores(child, texts, scores)
        return
    text = getattr(item, "text", None)
    if text:
        texts.append(str(text))
    confidence = _safe_float(getattr(item, "confidence", None))
    if confidence is not None:
        scores.append(confidence)


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    raise SystemExit(main())
