import unittest
import logging
from io import BytesIO
from types import SimpleNamespace

from PIL import Image

from backend.ingestion import IngestionPipeline
from backend.ingestion.models import ExtractedDocument, ExtractedPage, ImageAsset
from backend.ingestion.ocr_assets import OcrAssetProcessor
from backend.ingestion.pdf.embedded_image_extractor import EmbeddedPdfImageExtractor
from backend.ingestion.ocr_utils import should_skip_image, should_skip_image_dimensions


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
