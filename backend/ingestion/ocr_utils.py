"""OCR helpers for ingestion and auditability."""

from __future__ import annotations

import csv
import os
import signal
import subprocess
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from statistics import fmean
from typing import Any

from PIL import Image, ImageStat


_PIL_TESSERACT_ENCODE_LOCK = threading.Lock()


@dataclass(frozen=True)
class OcrResult:
    text: str
    confidence: float | None
    skipped: bool = False
    skip_reason: str = ""
    engine: str = "tesseract"
    fallback_from: str = ""
    error: str = ""


def should_skip_image(image: Image.Image, config: dict[str, Any]) -> tuple[bool, str]:
    width, height = image.size
    skip, reason = should_skip_image_dimensions(width, height, config)
    if skip:
        return skip, reason

    min_contrast = float(config.get("OCR_MIN_IMAGE_CONTRAST", 0.0))

    if min_contrast > 0:
        grayscale = image.convert("L")
        contrast = ImageStat.Stat(grayscale).stddev[0]
        if contrast < min_contrast:
            return True, f"image contrast too low ({contrast:.2f})"

    return False, ""


def should_skip_image_dimensions(width: int, height: int, config: dict[str, Any]) -> tuple[bool, str]:
    min_width = int(config.get("OCR_MIN_IMAGE_WIDTH", 20))
    min_height = int(config.get("OCR_MIN_IMAGE_HEIGHT", 20))
    min_area = int(config.get("OCR_MIN_IMAGE_AREA", 900))

    if width < min_width or height < min_height:
        return True, f"image too small ({width}x{height})"
    if width * height < min_area:
        return True, f"image area too small ({width * height})"

    return False, ""


def _config_value(config: dict[str, Any], key: str, default: Any = None) -> Any:
    getter = getattr(config, "get", None)
    if callable(getter):
        return getter(key, default)
    return config.get(key, default)


def _tesseract_command(config: dict[str, Any]) -> str:
    return os.environ.get("CIRCUITSHELF_TESSERACT_CMD") or "tesseract"


def _tesseract_timeout(config: dict[str, Any]) -> float:
    raw_timeout = _config_value(config, "OCR_TESSERACT_TIMEOUT_SECONDS", 120)
    try:
        return max(5.0, float(raw_timeout))
    except (TypeError, ValueError):
        return 120.0


def _tesseract_psm_args(config: dict[str, Any]) -> list[str]:
    psm = str(_config_value(config, "OCR_TESSERACT_PSM", "") or "").strip()
    return ["--psm", psm] if psm else []


def _save_tesseract_input(image: Image.Image, destination: Path) -> None:
    with _PIL_TESSERACT_ENCODE_LOCK:
        image.save(destination, format="PNG")


def _run_tesseract(input_path: Path, config: dict[str, Any], *, tsv: bool) -> subprocess.CompletedProcess[str]:
    command = [
        _tesseract_command(config),
        str(input_path),
        "stdout",
        *_tesseract_psm_args(config),
    ]
    if tsv:
        command.append("tsv")

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
        text=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=_tesseract_timeout(config))
    except subprocess.TimeoutExpired:
        _terminate_process_group(process)
        stdout, stderr = process.communicate()
        raise subprocess.TimeoutExpired(command, _tesseract_timeout(config), output=stdout, stderr=stderr)

    return subprocess.CompletedProcess(command, process.returncode, stdout=stdout, stderr=stderr)


def _terminate_process_group(process: subprocess.Popen[str]) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    except Exception:
        process.kill()


def parse_tesseract_tsv(tsv_text: str) -> tuple[str, float | None]:
    words: list[str] = []
    confidences: list[float] = []

    for row in csv.DictReader(tsv_text.splitlines(), delimiter="\t"):
        word = str(row.get("text", "")).strip()
        if not word:
            continue
        words.append(word)
        try:
            confidence = float(row.get("conf", ""))
        except (TypeError, ValueError):
            continue
        if confidence >= 0:
            confidences.append(confidence)

    return " ".join(words).strip(), fmean(confidences) if confidences else None


def _ocr_failure_result(reason: str) -> OcrResult:
    return OcrResult(text="", confidence=None, skipped=True, skip_reason=reason, engine="tesseract", error=reason)


def run_ocr(image: Image.Image, config: dict[str, Any]) -> OcrResult:
    skip, reason = should_skip_image(image, config)
    if skip:
        return OcrResult(text="", confidence=None, skipped=True, skip_reason=reason)

    try:
        with tempfile.TemporaryDirectory(prefix="circuitshelf_ocr_") as temp_dir:
            input_path = Path(temp_dir) / "input.png"
            _save_tesseract_input(image, input_path)

            use_confidence = bool(_config_value(config, "OCR_USE_TESSERACT_CONFIDENCE", True))
            completed = _run_tesseract(input_path, config, tsv=use_confidence)
            if completed.returncode != 0:
                error = (completed.stderr or completed.stdout or "unknown OCR failure").strip()
                return _ocr_failure_result(f"tesseract failed ({completed.returncode}): {error[:240]}")

            if use_confidence:
                text, confidence = parse_tesseract_tsv(completed.stdout)
                return OcrResult(text=text, confidence=confidence)

            return OcrResult(text=completed.stdout.strip(), confidence=None)
    except FileNotFoundError:
        return _ocr_failure_result(f"tesseract executable not found: {_tesseract_command(config)}")
    except subprocess.TimeoutExpired:
        return _ocr_failure_result(f"tesseract timed out after {_tesseract_timeout(config):.0f}s")
