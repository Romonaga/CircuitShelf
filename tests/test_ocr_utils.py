import unittest
import logging
from io import BytesIO
from types import SimpleNamespace

from PIL import Image

from backend.services.document_processing_service import DocumentProcessingService
from ocr_utils import should_skip_image, should_skip_image_dimensions
from pdf_visuals import RenderedPdfPage


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


class FakeState:
    def __init__(self):
        self.image_store = {}
        self.image_captions = {}
        self.image_page_text = {}

    def add_image_store(self, key, value):
        self.image_store[key] = value

    def add_image_caption(self, key, value):
        self.image_captions[key] = value

    def add_image_page_text(self, key, value):
        self.image_page_text[key] = value


class OcrUtilsTests(unittest.TestCase):
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

    def test_pdf_embedded_image_config_accepts_config_wrapper(self):
        service = DocumentProcessingService(
            config=ConfigWrapper({
                "OCR_MIN_IMAGE_WIDTH": 20,
                "OCR_MIN_IMAGE_HEIGHT": 20,
                "OCR_MIN_IMAGE_AREA": 900,
                "PDF_EMBEDDED_IMAGE_OCR_MIN_WIDTH": 80,
                "PDF_EMBEDDED_IMAGE_OCR_MIN_HEIGHT": 80,
                "PDF_EMBEDDED_IMAGE_OCR_MIN_AREA": 6400,
            }),
            trace_logger=None,
            state=None,
            chunker=None,
            token_utils=None,
            run_ocr=None,
            render_pdf_visual_pages=None,
            link_chunks_to_rendered_pages=None,
            detected_cpu_count=lambda: 32,
            reserved_core_count=lambda: 2,
            usable_core_count=lambda: 30,
            document_worker_count=lambda *_args, **_kwargs: 1,
            ocr_worker_count=lambda *_args, **_kwargs: 1,
            current_document_workers=lambda: 0,
            begin_document_worker=lambda *_args, **_kwargs: None,
            finish_document_worker=lambda *_args, **_kwargs: None,
            pdf_ext=".pdf",
        )

        config = service.pdf_embedded_image_ocr_config()

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

        service = DocumentProcessingService(
            config=ConfigWrapper({"OCR_TXT_DROP_SCORE": 0.4}),
            trace_logger=None,
            state=None,
            chunker=FakeChunker(),
            token_utils=None,
            run_ocr=fake_run_ocr,
            render_pdf_visual_pages=None,
            link_chunks_to_rendered_pages=None,
            detected_cpu_count=lambda: 32,
            reserved_core_count=lambda: 2,
            usable_core_count=lambda: 30,
            document_worker_count=lambda *_args, **_kwargs: 1,
            ocr_worker_count=lambda *_args, **_kwargs: 1,
            current_document_workers=lambda: 0,
            begin_document_worker=lambda *_args, **_kwargs: None,
            finish_document_worker=lambda *_args, **_kwargs: None,
            pdf_ext=".pdf",
        )
        image = Image.new("RGB", (120, 80), "white")
        raw = BytesIO()
        image.save(raw, format="PNG")

        result = service.ocr_pdf_image_job((0, 2, 1, raw.getvalue(), "demo.pdf_page3_img2"))

        self.assertFalse(result["ocr_result"]["accepted"])
        self.assertGreater(len(result["web_image_bytes"]), 0)

    def test_rendered_pdf_page_with_sparse_text_is_ocr_indexed(self):
        def fake_run_ocr(_image, _config):
            return SimpleNamespace(
                skipped=False,
                skip_reason="",
                confidence=88.0,
                text="555 timer pin 1 goes to ground and pin 8 connects to VCC for the astable circuit.",
            )

        def fake_render_pdf_visual_pages(_path, **_kwargs):
            image = Image.new("RGB", (180, 120), "white")
            raw = BytesIO()
            image.save(raw, format="PNG")
            return [
                RenderedPdfPage(
                    image_key="timer.pdf_page1_render",
                    page_number=1,
                    caption="Rendered page 1 from timer.pdf (raster page coverage 100%)",
                    searchable_text="Rendered page 1 from timer.pdf (raster page coverage 100%)",
                    image_bytes=raw.getvalue(),
                )
            ]

        logger = logging.getLogger("test-rendered-page-ocr")
        logger.addHandler(logging.NullHandler())
        state = FakeState()
        service = DocumentProcessingService(
            config=ConfigWrapper({
                "PDF_RENDER_VECTOR_PAGES": True,
                "PDF_RENDER_OCR_PAGES": True,
                "PDF_RENDER_MAX_PAGES_PER_DOC": 8,
                "PDF_RENDER_MIN_DRAWINGS": 100,
                "PDF_RENDER_ZOOM": 1.5,
                "PDF_RENDER_RASTER_PAGES": True,
                "PDF_RENDER_MIN_RASTER_COVERAGE": 0.8,
                "OCR_TXT_DROP_SCORE": 0.4,
                "OCR_INDEX_TEXT_MIN_CHARS": 20,
                "INDEX_IMAGE_OCR_AS_TEXT": True,
            }),
            trace_logger=logger,
            state=state,
            chunker=FakeChunker(),
            token_utils=None,
            run_ocr=fake_run_ocr,
            render_pdf_visual_pages=fake_render_pdf_visual_pages,
            link_chunks_to_rendered_pages=None,
            detected_cpu_count=lambda: 32,
            reserved_core_count=lambda: 2,
            usable_core_count=lambda: 30,
            document_worker_count=lambda *_args, **_kwargs: 1,
            ocr_worker_count=lambda *_args, **_kwargs: 1,
            current_document_workers=lambda: 0,
            begin_document_worker=lambda *_args, **_kwargs: None,
            finish_document_worker=lambda *_args, **_kwargs: None,
            pdf_ext=".pdf",
        )
        extra_chunks, extra_sources, extra_meta = [], [], []

        rendered_count = service.add_pdf_rendered_pages(
            "training/timer.pdf",
            state,
            extra_chunks=extra_chunks,
            extra_sources=extra_sources,
            extra_meta=extra_meta,
        )

        self.assertEqual(rendered_count, 1)
        self.assertIn("timer.pdf_page1_render", state.image_store)
        self.assertIn("pin 1 goes to ground", state.image_page_text["timer.pdf_page1_render"])
        self.assertEqual(extra_chunks, ["555 timer pin 1 goes to ground and pin 8 connects to VCC for the astable circuit."])
        self.assertEqual(extra_sources, ["training/timer.pdf"])
        self.assertEqual(extra_meta[0]["source_image_id"], "timer.pdf_page1_render")
        self.assertEqual(extra_meta[0]["page"], 1)


if __name__ == "__main__":
    unittest.main()
