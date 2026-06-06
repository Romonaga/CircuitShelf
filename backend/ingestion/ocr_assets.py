from __future__ import annotations

import base64
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
from typing import Any

from PIL import Image


_PNG_NORMALIZE_LOCK = threading.Lock()


class OcrAssetProcessor:
    def __init__(
        self,
        *,
        config: Any,
        chunker: Any,
        run_ocr,
        trace_logger=None,
        ocr_worker_count=lambda item_count, **_kwargs: 1,
        current_document_workers=lambda: 0,
        detected_cpu_count=lambda: 1,
        reserved_core_count=lambda *_args, **_kwargs: 0,
    ):
        self.config = config
        self.chunker = chunker
        self.run_ocr = run_ocr
        self.trace_logger = trace_logger or logging.getLogger(__name__)
        self.ocr_worker_count = ocr_worker_count
        self.current_document_workers = current_document_workers
        self.detected_cpu_count = detected_cpu_count
        self.reserved_core_count = reserved_core_count

    def ocr_image_bytes(self, image_bytes: bytes, image_id: str) -> dict:
        with Image.open(BytesIO(image_bytes)) as opened:
            image = opened.convert("RGB")
        result = self.run_ocr(image, self.config)
        if result.skipped:
            return {
                "accepted": False,
                "text": "",
                "score": 0.0,
                "reason": result.skip_reason,
                "confidence": result.confidence,
                "skipped": True,
            }

        cleaned_text = self.chunker.clean_ocr_text(result.text)
        score, reason = self.chunker.evaluate_ocr_quality(cleaned_text, result.confidence)
        accepted = score >= self.config.get("OCR_TXT_DROP_SCORE", 0.4)
        return {
            "accepted": accepted,
            "text": cleaned_text,
            "score": score,
            "reason": reason,
            "confidence": result.confidence,
            "skipped": False,
        }

    def image_bytes_to_png_bytes(self, image_bytes: bytes, image_id: str = "image") -> bytes:
        try:
            with Image.open(BytesIO(image_bytes)) as image:
                if image.mode not in ("RGB", "RGBA"):
                    image = image.convert("RGBA" if "transparency" in image.info else "RGB")
                output = BytesIO()
                with _PNG_NORMALIZE_LOCK:
                    image.save(output, format="PNG")
                return output.getvalue()
        except Exception as exc:
            self.trace_logger.warning(f"Could not normalize {image_id} to PNG for web display: {exc}")
            return image_bytes

    @staticmethod
    def base64_image(image_bytes: bytes) -> str:
        return base64.b64encode(image_bytes).decode("utf-8")

    def worker_count(self, item_count: int) -> int:
        if not self.config.get("USE_MULTITHREAD_OCR", False) or item_count <= 1:
            return 1
        return self.ocr_worker_count(
            item_count,
            active_document_workers=self.current_document_workers(),
            cpu_count=self.detected_cpu_count(),
        )

    def run_jobs(self, jobs: list[tuple]) -> list[dict]:
        if not jobs:
            return []
        workers = self.worker_count(len(jobs))
        if workers <= 1:
            return [self._run_job(job) for job in jobs]

        self.trace_logger.debug(
            f"OCR processing {len(jobs)} images with {workers} workers "
            f"({self.detected_cpu_count()} cores, reserving {self.reserved_core_count(self.detected_cpu_count())})"
        )
        results = []
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(self._run_job, job): job for job in jobs}
            for future in as_completed(futures):
                job = futures[future]
                try:
                    results.append(future.result())
                except Exception as exc:
                    self.trace_logger.warning(f"OCR worker failed for {job[3]}: {exc}")
        results.sort(key=lambda item: item["order"])
        return results

    def _run_job(self, job: tuple) -> dict:
        order, page_number, image_bytes, image_key, source_kind = job
        web_image_bytes = self.image_bytes_to_png_bytes(image_bytes, image_key)
        ocr_result = self.ocr_image_bytes(web_image_bytes, image_key)
        return {
            "order": order,
            "page_number": page_number,
            "image_key": image_key,
            "source_kind": source_kind,
            "image_bytes": web_image_bytes,
            "ocr_result": ocr_result,
        }
