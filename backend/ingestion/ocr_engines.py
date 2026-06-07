"""Selectable OCR engines for ingestion.

Tesseract remains the stable default. Optional engines are loaded lazily so a
missing GPU OCR dependency never prevents CircuitShelf from starting.
"""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from statistics import fmean
from typing import Any

from PIL import Image

from backend.ingestion.ocr_utils import OcrResult, run_ocr as run_tesseract_ocr, should_skip_image


_PADDLE_LOCK = threading.Lock()
_PADDLE_ENGINES: dict[tuple[str, str, str], Any] = {}


def run_selected_ocr(image: Image.Image, config: dict[str, Any]) -> OcrResult:
    """Run OCR using the configured engine.

    Supported values:
    - tesseract: CPU Tesseract CLI, stable default.
    - paddleocr: optional PaddleOCR GPU/CPU backend.
    """

    engine = _normalized_engine(config)
    if engine == "tesseract":
        return run_tesseract_ocr(image, config)
    if engine == "paddleocr":
        return _run_paddle_ocr_with_fallback(image, config)
    return OcrResult(text="", confidence=None, skipped=True, skip_reason=f"unsupported OCR engine: {engine}")


def ocr_uses_local_gpu(config: dict[str, Any]) -> bool:
    """Return true when the selected OCR engine will consume local CUDA resources."""

    return _normalized_engine(config) == "paddleocr" and _paddle_device(config) == "gpu"


def _run_paddle_ocr_with_fallback(image: Image.Image, config: dict[str, Any]) -> OcrResult:
    skip, reason = should_skip_image(image, config)
    if skip:
        return OcrResult(text="", confidence=None, skipped=True, skip_reason=reason)

    try:
        return _run_paddle_ocr(image, config)
    except Exception as exc:
        fallback = bool(_config_value(config, "OCR_ENGINE_FALLBACK", True))
        if fallback:
            return run_tesseract_ocr(image, config)
        return OcrResult(
            text="",
            confidence=None,
            skipped=True,
            skip_reason=f"paddleocr failed: {str(exc)[:240]}",
        )


def _run_paddle_ocr(image: Image.Image, config: dict[str, Any]) -> OcrResult:
    external_python = str(_config_value(config, "PADDLEOCR_PYTHON", "") or "").strip()
    if external_python:
        return _run_external_paddle_ocr(image, config, external_python)

    ocr = _paddle_engine(config)
    np = importlib.import_module("numpy")
    rgb = image.convert("RGB")
    input_image = np.asarray(rgb)

    with _PADDLE_LOCK:
        if hasattr(ocr, "predict"):
            raw_result = ocr.predict(input_image)
        else:
            raw_result = ocr.ocr(input_image, cls=True)

    text, confidence = _extract_paddle_text_and_confidence(raw_result)
    return OcrResult(text=text, confidence=confidence)


def _run_external_paddle_ocr(image: Image.Image, config: dict[str, Any], python_path: str) -> OcrResult:
    runner_path = Path(__file__).with_name("paddleocr_runner.py")
    with tempfile.NamedTemporaryFile(suffix=".png", delete=True) as image_file:
        image.convert("RGB").save(image_file.name, format="PNG")
        command = [
            python_path,
            str(runner_path),
            "--image",
            image_file.name,
            "--lang",
            str(_config_value(config, "PADDLEOCR_LANG", "en") or "en"),
            "--device",
            _paddle_device(config),
        ]
        engine = str(_config_value(config, "PADDLEOCR_ENGINE", "") or "").strip()
        if engine:
            command.extend(["--engine", engine])
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=float(_config_value(config, "PADDLEOCR_TIMEOUT_SECONDS", 120) or 120),
        )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "unknown error").strip()
        raise RuntimeError(f"external paddleocr exited {completed.returncode}: {detail[:500]}")
    try:
        payload = json.loads(completed.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"external paddleocr returned invalid JSON: {completed.stdout[:500]}") from exc
    return OcrResult(text=str(payload.get("text") or ""), confidence=_safe_float(payload.get("confidence")))


def _paddle_engine(config: dict[str, Any]) -> Any:
    paddleocr_module = importlib.import_module("paddleocr")
    paddle_ocr = getattr(paddleocr_module, "PaddleOCR")
    lang = str(_config_value(config, "PADDLEOCR_LANG", "en") or "en")
    device = _paddle_device(config)
    engine = str(_config_value(config, "PADDLEOCR_ENGINE", "") or "").strip()
    key = (lang, device, engine)
    cached = _PADDLE_ENGINES.get(key)
    if cached is not None:
        return cached

    kwargs: dict[str, Any] = {"lang": lang, "device": device}
    if engine:
        kwargs["engine"] = engine
    try:
        instance = paddle_ocr(**kwargs)
    except TypeError:
        # PaddleOCR 2.x used use_gpu instead of the 3.x device parameter.
        legacy_kwargs: dict[str, Any] = {"lang": lang, "use_gpu": device == "gpu"}
        instance = paddle_ocr(**legacy_kwargs)
    _PADDLE_ENGINES[key] = instance
    return instance


def clear_ocr_engine_cache() -> None:
    """Clear cached OCR engine instances. Primarily used by tests."""

    _PADDLE_ENGINES.clear()


def _extract_paddle_text_and_confidence(raw_result: Any) -> tuple[str, float | None]:
    texts: list[str] = []
    scores: list[float] = []

    for item in _iter_result_items(raw_result):
        _collect_text_scores(item, texts, scores)

    cleaned = " ".join(text.strip() for text in texts if str(text).strip()).strip()
    return cleaned, fmean(scores) * 100 if scores and max(scores) <= 1.0 else (fmean(scores) if scores else None)


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
                scores.extend(_safe_float(score) for score in rec_scores if _safe_float(score) is not None)
            return
        text = item.get("text") or item.get("transcription")
        if text:
            texts.append(str(text))
        score = item.get("score") or item.get("confidence")
        parsed_score = _safe_float(score)
        if parsed_score is not None:
            scores.append(parsed_score)
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


def _normalized_engine(config: dict[str, Any]) -> str:
    return str(_config_value(config, "OCR_ENGINE", "tesseract") or "tesseract").strip().lower()


def _paddle_device(config: dict[str, Any]) -> str:
    configured = str(_config_value(config, "PADDLEOCR_DEVICE", "") or "").strip().lower()
    if configured in {"cpu", "gpu"}:
        return configured
    return "gpu" if bool(_config_value(config, "PADDLEOCR_USE_GPU", True)) else "cpu"


def _config_value(config: dict[str, Any], key: str, default: Any = None) -> Any:
    getter = getattr(config, "get", None)
    if callable(getter):
        return getter(key, default)
    return config.get(key, default)
