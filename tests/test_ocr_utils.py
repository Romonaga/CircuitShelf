import unittest
import logging
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from backend.ingestion import IngestionPipeline
from backend.ingestion.models import ExtractedDocument, ExtractedPage, ImageAsset
from backend.ingestion.ocr_assets import OcrAssetProcessor
from backend.ingestion.pdf.embedded_image_extractor import EmbeddedPdfImageExtractor
from backend.ingestion.pdf.extractor import PdfDocumentExtractor
from backend.ingestion.ocr_engines import (
    _external_paddleocr_python,
    _extract_paddle_text_and_confidence,
    _paddleocr_kwargs,
    clear_ocr_engine_cache,
    ocr_uses_local_gpu,
    run_selected_ocr,
    selected_ocr_mode,
)
from backend.ingestion.ocr_utils import parse_tesseract_tsv, should_skip_image, should_skip_image_dimensions
from backend.services.gpu_work_queue import resolve_local_gpu_ocr_pending_cap, resolve_local_gpu_ocr_slots


class ConfigWrapper:
    def __init__(self, values):
        self.config = dict(values)

    def get(self, key, default=None):
        return self.config.get(key, default)

    def __getitem__(self, key):
        if key not in self.config:
            raise KeyError(f"Missing required config key: {key!r}")
        return self.config[key]


class FakeChunker:
    def clean_ocr_text(self, text):
        return text

    def evaluate_ocr_quality(self, text, confidence):
        if "pin" in text.lower() or "vcc" in text.lower():
            return 0.9, ""
        return 0.1, "low OCR quality"

    def make_chunk_meta(self, text, source_file, section, chunk_type):
        return {
            "section": section,
            "page": 1,
            "source": source_file,
            "category": "General Information",
            "chunk_type": chunk_type,
            "token_count": len(text.split()),
            "quality_score": 1.0,
            "quality_flags": [],
        }

    def smart_chunk_pages(self, _page_texts, _source_file):
        return [], []


class FakeState:
    def __init__(self):
        self.image_store = {}
        self.image_captions = {}
        self.image_mime_types = {}
        self.image_page_text = {}
        self.chunks = []
        self.sources = []
        self.metadata = []

    def add_image_store(self, key, value):
        self.image_store[key] = value

    def add_image_caption(self, key, value):
        self.image_captions[key] = value

    def add_image_mime_type(self, key, value):
        self.image_mime_types[key] = value

    def add_image_page_text(self, key, value):
        self.image_page_text[key] = value

    def extend_chunks(self, chunks, sources, metadata):
        self.chunks.extend(chunks)
        self.sources.extend(sources)
        self.metadata.extend(metadata)


class FakeTokenUtils:
    @staticmethod
    def estimate_token_density(_text):
        return 1.0


class OcrUtilsTests(unittest.TestCase):
    def test_parse_tesseract_tsv_extracts_text_and_confidence(self):
        text, confidence = parse_tesseract_tsv(
            "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
            "5\t1\t1\t1\t1\t1\t0\t0\t10\t10\t92.5\tVCC\n"
            "5\t1\t1\t1\t1\t2\t12\t0\t10\t10\t88\tGND\n"
            "5\t1\t1\t1\t1\t3\t24\t0\t10\t10\t-1\t\n"
        )

        self.assertEqual(text, "VCC GND")
        self.assertAlmostEqual(confidence, 90.25)

    def test_should_skip_tiny_image(self):
        image = Image.new("RGB", (10, 10), "white")

        skip, reason = should_skip_image(
            image,
            {
                "OCR_MIN_IMAGE_WIDTH": 20,
                "OCR_MIN_IMAGE_HEIGHT": 20,
                "OCR_MIN_IMAGE_AREA": 900,
            },
        )

        self.assertTrue(skip)
        self.assertIn("too small", reason)

    def test_should_allow_reasonable_image(self):
        image = Image.new("RGB", (40, 40), "white")

        skip, reason = should_skip_image(
            image,
            {
                "OCR_MIN_IMAGE_WIDTH": 20,
                "OCR_MIN_IMAGE_HEIGHT": 20,
                "OCR_MIN_IMAGE_AREA": 900,
            },
        )

        self.assertFalse(skip)
        self.assertEqual(reason, "")

    def test_should_skip_dimensions_without_decoding_image(self):
        skip, reason = should_skip_image_dimensions(
            12,
            80,
            {
                "OCR_MIN_IMAGE_WIDTH": 20,
                "OCR_MIN_IMAGE_HEIGHT": 20,
                "OCR_MIN_IMAGE_AREA": 900,
            },
        )

        self.assertTrue(skip)
        self.assertIn("too small", reason)

    def test_should_allow_dimensions_without_decoding_image(self):
        skip, reason = should_skip_image_dimensions(
            120,
            80,
            {
                "OCR_MIN_IMAGE_WIDTH": 20,
                "OCR_MIN_IMAGE_HEIGHT": 20,
                "OCR_MIN_IMAGE_AREA": 900,
            },
        )

        self.assertFalse(skip)
        self.assertEqual(reason, "")

    def test_unsupported_ocr_engine_returns_skipped_result(self):
        image = Image.new("RGB", (120, 80), "white")

        result = run_selected_ocr(
            image,
            {
                "OCR_ENGINE": "unknown",
                "OCR_MIN_IMAGE_WIDTH": 20,
                "OCR_MIN_IMAGE_HEIGHT": 20,
                "OCR_MIN_IMAGE_AREA": 900,
            },
        )

        self.assertTrue(result.skipped)
        self.assertIn("unsupported OCR engine", result.skip_reason)

    def test_paddleocr_gpu_engine_reports_local_gpu_use(self):
        self.assertTrue(ocr_uses_local_gpu({
            "OCR_ENGINE": "paddleocr",
            "PADDLEOCR_DEVICE": "gpu",
        }))
        self.assertTrue(ocr_uses_local_gpu({"OCR_ENGINE": "paddleocr", "PADDLEOCR_DEVICE": "cpu"}))
        self.assertFalse(ocr_uses_local_gpu({
            "OCR_ENGINE": "tesseract",
            "PADDLEOCR_DEVICE": "gpu",
        }))

    def test_selected_ocr_mode_reports_effective_engine_and_device(self):
        self.assertEqual(
            selected_ocr_mode({"OCR_ENGINE": "tesseract", "PADDLEOCR_DEVICE": "gpu"}),
            {"ocrEngine": "tesseract", "ocrDevice": "cpu", "ocrMode": "tesseract/cpu"},
        )
        self.assertEqual(
            selected_ocr_mode({"OCR_ENGINE": "paddleocr", "PADDLEOCR_DEVICE": "gpu"}),
            {"ocrEngine": "paddleocr", "ocrDevice": "gpu", "ocrMode": "paddleocr/gpu"},
        )
        self.assertEqual(
            selected_ocr_mode({"OCR_ENGINE": "paddleocr", "PADDLEOCR_DEVICE": "cpu"}),
            {"ocrEngine": "paddleocr", "ocrDevice": "gpu", "ocrMode": "paddleocr/gpu"},
        )

    def test_paddleocr_failure_falls_back_to_tesseract_when_enabled(self):
        image = Image.new("RGB", (120, 80), "white")

        with (
            patch("backend.ingestion.ocr_engines._run_paddle_ocr", side_effect=RuntimeError("missing paddle")),
            patch("backend.ingestion.ocr_engines.run_tesseract_ocr", return_value=SimpleNamespace(text="fallback text", confidence=90.0, skipped=False, skip_reason="")),
        ):
            result = run_selected_ocr(
                image,
                {
                    "OCR_ENGINE": "paddleocr",
                    "OCR_ENGINE_FALLBACK": True,
                    "OCR_MIN_IMAGE_WIDTH": 20,
                    "OCR_MIN_IMAGE_HEIGHT": 20,
                    "OCR_MIN_IMAGE_AREA": 900,
                },
            )

        self.assertFalse(result.skipped)
        self.assertEqual(result.text, "fallback text")

    def test_paddleocr_failure_always_falls_back_to_tesseract(self):
        image = Image.new("RGB", (120, 80), "white")
        clear_ocr_engine_cache()

        with (
            patch("backend.ingestion.ocr_engines._run_paddle_ocr", side_effect=RuntimeError("missing paddle")),
            patch("backend.ingestion.ocr_engines.run_tesseract_ocr", return_value=SimpleNamespace(text="fallback text", confidence=90.0, skipped=False, skip_reason="")),
        ):
            result = run_selected_ocr(
                image,
                {
                    "OCR_ENGINE": "paddleocr",
                    "OCR_ENGINE_FALLBACK": False,
                    "OCR_MIN_IMAGE_WIDTH": 20,
                    "OCR_MIN_IMAGE_HEIGHT": 20,
                    "OCR_MIN_IMAGE_AREA": 900,
                },
            )

        self.assertFalse(result.skipped)
        self.assertEqual(result.text, "fallback text")
        self.assertEqual(result.fallback_from, "paddleocr")

    def test_repeated_paddle_failures_open_circuit_breaker(self):
        image = Image.new("RGB", (120, 80), "white")
        clear_ocr_engine_cache()

        with (
            patch("backend.ingestion.ocr_engines._run_paddle_ocr", side_effect=RuntimeError("paddle wedged")) as paddle_mock,
            patch("backend.ingestion.ocr_engines.run_tesseract_ocr", return_value=SimpleNamespace(text="fallback text", confidence=90.0, skipped=False, skip_reason="")),
        ):
            results = [
                run_selected_ocr(
                    image,
                    {
                        "OCR_ENGINE": "paddleocr",
                        "OCR_MIN_IMAGE_WIDTH": 20,
                        "OCR_MIN_IMAGE_HEIGHT": 20,
                        "OCR_MIN_IMAGE_AREA": 900,
                    },
                )
                for _ in range(4)
            ]

        self.assertEqual(paddle_mock.call_count, 3)
        self.assertTrue(all(result.fallback_from == "paddleocr" for result in results))
        self.assertIn("circuit breaker", results[-1].error)
        self.assertIn("paddle wedged", results[-1].error)

    @patch.dict("os.environ", {"CIRCUITSHELF_PADDLEOCR_PYTHON": "/tmp/ocr-python"})
    def test_paddleocr_external_python_runner_is_supported(self):
        image = Image.new("RGB", (120, 80), "white")

        completed = SimpleNamespace(returncode=0, stdout='{"text":"VCC GND","confidence":91.5}\n', stderr="")
        with patch("backend.ingestion.ocr_engines._run_external_ocr_command", return_value=completed) as run_mock:
            result = run_selected_ocr(
                image,
                {
                    "OCR_ENGINE": "paddleocr",
                    "PADDLEOCR_DEVICE": "gpu",
                    "PADDLEOCR_LANG": "en",
                    "OCR_MIN_IMAGE_WIDTH": 20,
                    "OCR_MIN_IMAGE_HEIGHT": 20,
                    "OCR_MIN_IMAGE_AREA": 900,
                },
            )

        self.assertFalse(result.skipped)
        self.assertEqual(result.text, "VCC GND")
        self.assertEqual(result.confidence, 91.5)
        self.assertEqual(run_mock.call_args.args[0][0], "/tmp/ocr-python")

    @patch.dict("os.environ", {}, clear=True)
    def test_paddleocr_external_python_defaults_to_ocr_venv(self):
        with patch("backend.ingestion.ocr_engines.Path.exists", return_value=True):
            self.assertTrue(_external_paddleocr_python().endswith(".venv-ocr/bin/python"))

    def test_paddleocr_result_normalization_handles_current_json_shape(self):
        text, confidence = _extract_paddle_text_and_confidence(
            [
                {
                    "res": {
                        "rec_texts": ["VCC", "GND"],
                        "rec_scores": [0.96, 0.84],
                    }
                }
            ]
        )

        self.assertEqual(text, "VCC GND")
        self.assertAlmostEqual(confidence, 90.0)

    def test_paddleocr_kwargs_disable_document_preprocessors(self):
        kwargs = _paddleocr_kwargs(lang="en", device="gpu")

        self.assertEqual(kwargs["lang"], "en")
        self.assertEqual(kwargs["device"], "gpu")
        self.assertFalse(kwargs["use_doc_orientation_classify"])
        self.assertFalse(kwargs["use_doc_unwarping"])
        self.assertFalse(kwargs["use_textline_orientation"])

    def test_pdf_ocr_stats_roll_up_fallback_errors(self):
        stats = PdfDocumentExtractor._ocr_stats([
            {
                "ocr_result": {
                    "accepted": True,
                    "skipped": False,
                    "engine": "tesseract",
                    "fallbackFrom": "paddleocr",
                    "error": "external paddleocr exited 1: runtime failure",
                }
            },
            {
                "ocr_result": {
                    "accepted": False,
                    "skipped": True,
                    "engine": "tesseract",
                    "fallbackFrom": "paddleocr",
                    "error": "external paddleocr exited 1: runtime failure",
                }
            },
        ])

        self.assertEqual(stats["ocrFallbacks"], 2)
        self.assertIn("external paddleocr exited 1: runtime failure (2)", stats["ocrFallbackErrors"])

    def test_gpu_ocr_worker_count_uses_gpu_lane_count(self):
        ocr_assets = OcrAssetProcessor(
            config=ConfigWrapper({
                "USE_MULTITHREAD_OCR": True,
                "OCR_ENGINE": "paddleocr",
                "PADDLEOCR_DEVICE": "gpu",
            }),
            trace_logger=None,
            chunker=FakeChunker(),
            run_ocr=lambda *_args, **_kwargs: None,
            detected_cpu_count=lambda: 32,
            reserved_core_count=lambda *_args, **_kwargs: 2,
            ocr_worker_count=lambda *_args, **_kwargs: 2,
            current_document_workers=lambda: 15,
            local_gpu_ocr_slots=lambda: 8,
        )

        self.assertEqual(ocr_assets.worker_count(20), 8)

    def test_auto_gpu_ocr_slots_are_conservative(self):
        self.assertEqual(
            resolve_local_gpu_ocr_slots(
                ConfigWrapper({"LOCAL_GPU_OCR_SLOTS": "auto"}),
                detected_gpus=1,
                gpu_memory_total_mib=10 * 1024,
            ),
            1,
        )
        self.assertEqual(
            resolve_local_gpu_ocr_slots(
                ConfigWrapper({"LOCAL_GPU_OCR_SLOTS": "auto"}),
                detected_gpus=1,
                gpu_memory_total_mib=16 * 1024,
            ),
            2,
        )
        self.assertEqual(
            resolve_local_gpu_ocr_slots(
                ConfigWrapper({"LOCAL_GPU_OCR_SLOTS": "auto"}),
                detected_gpus=1,
                gpu_memory_total_mib=24 * 1024,
            ),
            3,
        )
        self.assertEqual(
            resolve_local_gpu_ocr_slots(
                ConfigWrapper({"LOCAL_GPU_OCR_SLOTS": "auto"}),
                detected_gpus=4,
                gpu_memory_total_mib=48 * 1024,
            ),
            16,
        )
        self.assertEqual(resolve_local_gpu_ocr_slots(ConfigWrapper({"LOCAL_GPU_OCR_SLOTS": "8"}), detected_gpus=1), 8)

    def test_auto_gpu_ocr_pending_cap_uses_vram_class(self):
        self.assertEqual(
            resolve_local_gpu_ocr_pending_cap(
                ConfigWrapper({}),
                ocr_slots=1,
                detected_gpus=1,
                gpu_memory_total_mib=10 * 1024,
            ),
            2,
        )
        self.assertEqual(
            resolve_local_gpu_ocr_pending_cap(
                ConfigWrapper({}),
                ocr_slots=3,
                detected_gpus=1,
                gpu_memory_total_mib=24 * 1024,
            ),
            8,
        )

    def test_cpu_ocr_worker_count_keeps_cpu_budget_sizing(self):
        ocr_assets = OcrAssetProcessor(
            config=ConfigWrapper({
                "USE_MULTITHREAD_OCR": True,
                "OCR_ENGINE": "tesseract",
                "PADDLEOCR_DEVICE": "gpu",
            }),
            trace_logger=None,
            chunker=FakeChunker(),
            run_ocr=lambda *_args, **_kwargs: None,
            detected_cpu_count=lambda: 32,
            reserved_core_count=lambda *_args, **_kwargs: 2,
            ocr_worker_count=lambda *_args, **_kwargs: 2,
            current_document_workers=lambda: 15,
            local_gpu_ocr_slots=lambda: 8,
        )

        self.assertEqual(ocr_assets.worker_count(20), 2)

    def test_pdf_embedded_image_config_accepts_config_wrapper(self):
        extractor = EmbeddedPdfImageExtractor(
            config=ConfigWrapper({
                "OCR_MIN_IMAGE_WIDTH": 20,
                "OCR_MIN_IMAGE_HEIGHT": 20,
                "OCR_MIN_IMAGE_AREA": 900,
                "PDF_EMBEDDED_IMAGE_OCR_MIN_WIDTH": 80,
                "PDF_EMBEDDED_IMAGE_OCR_MIN_HEIGHT": 80,
                "PDF_EMBEDDED_IMAGE_OCR_MIN_AREA": 6400,
            }),
        )

        config = extractor._embedded_image_config()

        self.assertEqual(config["OCR_MIN_IMAGE_WIDTH"], 80)
        self.assertEqual(config["OCR_MIN_IMAGE_HEIGHT"], 80)
        self.assertEqual(config["OCR_MIN_IMAGE_AREA"], 6400)

    def test_pdf_image_job_keeps_visual_asset_when_ocr_text_is_rejected(self):
        def fake_run_ocr(_image, _config):
            return SimpleNamespace(
                skipped=False,
                skip_reason="",
                confidence=42.0,
                text="noise",
            )

        ocr_assets = OcrAssetProcessor(
            config=ConfigWrapper({"OCR_TXT_DROP_SCORE": 0.4}),
            trace_logger=None,
            chunker=FakeChunker(),
            run_ocr=fake_run_ocr,
            detected_cpu_count=lambda: 32,
            reserved_core_count=lambda: 2,
            ocr_worker_count=lambda *_args, **_kwargs: 1,
            current_document_workers=lambda: 0,
        )
        image = Image.new("RGB", (120, 80), "white")
        raw = BytesIO()
        image.save(raw, format="PNG")

        result = ocr_assets.run_jobs([(0, 3, raw.getvalue(), "demo.pdf_page3_img2", "embedded")])[0]

        self.assertFalse(result["ocr_result"]["accepted"])
        self.assertGreater(len(result["image_bytes"]), 0)

    def test_rendered_pdf_page_with_sparse_text_is_ocr_indexed(self):
        logger = logging.getLogger("test-rendered-page-ocr")
        logger.addHandler(logging.NullHandler())
        state = FakeState()
        pipeline = IngestionPipeline(
            config=ConfigWrapper({
                "OCR_INDEX_TEXT_MIN_CHARS": 20,
                "INDEX_IMAGE_OCR_AS_TEXT": True,
            }),
            trace_logger=logger,
            run_ocr=None,
            detected_cpu_count=lambda: 32,
            reserved_core_count=lambda: 2,
            usable_core_count=lambda: 30,
            document_worker_count=lambda *_args, **_kwargs: 1,
            ocr_worker_count=lambda *_args, **_kwargs: 1,
            current_document_workers=lambda: 0,
            local_gpu_ocr_slots=lambda: 1,
            begin_document_worker=lambda *_args, **_kwargs: None,
            finish_document_worker=lambda *_args, **_kwargs: None,
            pdf_ext=".pdf",
        )
        image = Image.new("RGB", (180, 120), "white")
        raw = BytesIO()
        image.save(raw, format="PNG")
        document = ExtractedDocument(
            source_path="training/timer.pdf",
            pages=[ExtractedPage(page_number=1, text="Rendered page 1 from timer.pdf")],
            assets=[
                ImageAsset(
                    image_key="timer.pdf_page1_render",
                    page_number=1,
                    caption="Rendered page 1 from timer.pdf",
                    image_bytes=raw.getvalue(),
                    searchable_text="Rendered page 1 from timer.pdf\n555 timer pin 1 goes to ground and pin 8 connects to VCC.",
                    ocr_text="555 timer pin 1 goes to ground and pin 8 connects to VCC.",
                    ocr_score=0.9,
                    ocr_confidence=88.0,
                    source_kind="rendered",
                )
            ],
        )

        pipeline._store_extracted_document(document, state, FakeChunker(), FakeTokenUtils())

        self.assertIn("timer.pdf_page1_render", state.image_store)
        self.assertIn("pin 1 goes to ground", state.image_page_text["timer.pdf_page1_render"])
        self.assertEqual(state.chunks, ["555 timer pin 1 goes to ground and pin 8 connects to VCC."])
        self.assertEqual(state.sources, ["training/timer.pdf"])
        self.assertEqual(state.metadata[0]["source_image_id"], "timer.pdf_page1_render")
        self.assertEqual(state.metadata[0]["page"], 1)


if __name__ == "__main__":
    unittest.main()
