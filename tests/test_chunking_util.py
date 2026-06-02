import logging
import unittest

from chunking_util import ChunkingUtils


class FakeTokenUtils:
    @staticmethod
    def tokenize_len(text):
        return len(str(text).replace("\n", " ").split())


class FakeConfig(dict):
    def get(self, key, default=None):
        return super().get(key, default)


class ChunkingUtilTests(unittest.TestCase):
    def setUp(self):
        self.logger = logging.getLogger("test-chunking")
        self.logger.addHandler(logging.NullHandler())
        self.config = FakeConfig({
            "CHUNK_SIZE": 45,
            "CHUNK_OVERLAP": 8,
            "MIN_TOKENS_PER_CHUNK": 5,
            "MIN_CHUNK_QUALITY": 0.15,
            "CHUNKING_MODE": "deterministic",
            "OCR_TXT_DROP_SCORE": 0.4,
            "OCR_MIN_MEANINGFUL_CHARS": 80,
            "OCR_MIN_MEANINGFUL_WORDS": 6,
            "OCR_SHORT_TEXT_MAX_SCORE": 0.3,
            "OCR_LOW_CONTENT_MAX_SCORE": 0.2,
            "CHUNK_CATEGORIES": {
                "HIGH_LEVEL_DETAIL": {"keywords": ["overview", "features"]},
                "MED_LEVEL_DETAIL": {"keywords": ["application", "operation"]},
                "TECH_LEVEL_DETAIL": {"keywords": ["pin", "threshold", "equation", "timing"]},
            },
            "EQUATION_DETECTION": {
                "MATH_SYMBOLS": ["=", "<", ">"],
                "KEYWORDS": ["frequency", "timing", "equation"],
            },
        })
        self.chunker = ChunkingUtils(None, FakeTokenUtils(), self.logger, self.config)

    def test_normalize_extracted_text_removes_dot_leader_noise(self):
        text = """
        ........................................................................ 1
        Product Folder Links: NA555 NE555
        The xx555 timer is a popular precision timer.
        """

        cleaned = self.chunker.normalize_extracted_text(text)

        self.assertNotIn("....", cleaned)
        self.assertIn("precision timer", cleaned)

    def test_deterministic_chunking_adds_quality_metadata(self):
        text = """
        8 Detailed Description
        The xx555 timer is a popular precision timer for timing applications.
        The trigger pin starts timing and the threshold pin stops timing.
        """

        chunks, meta = self.chunker.smart_chunk_text(text, "ne555.pdf")

        self.assertEqual(len(chunks), 1)
        self.assertEqual(meta[0]["section"], "8 Detailed Description")
        self.assertEqual(meta[0]["category"], "TECH_LEVEL_DETAIL")
        self.assertIn("quality_score", meta[0])
        self.assertIn("chunk_type", meta[0])

    def test_make_chunk_meta_categorizes_ocr_text(self):
        meta = self.chunker.make_chunk_meta(
            "Component wiring: LED1(A) => J27 and resistor pin goes to ground",
            "book.pdf",
            "Image OCR",
            "ocr",
        )

        self.assertEqual(meta["section"], "Image OCR")
        self.assertEqual(meta["chunk_type"], "ocr")
        self.assertEqual(meta["category"], "TECH_LEVEL_DETAIL")
        self.assertGreater(meta["quality_score"], 0)

    def test_filter_chunks_drops_low_quality_metadata(self):
        chunks, sources, metadata = self.chunker.filter_chunks(
            ["valid timer pin chunk", ".................................... 1"],
            ["a.pdf", "a.pdf"],
            [{"quality_score": 1.0}, {"quality_score": 0.0}],
            min_tokens=1,
            max_tokens=100,
        )

        self.assertEqual(chunks, ["valid timer pin chunk"])
        self.assertEqual(sources, ["a.pdf"])
        self.assertEqual(metadata, [{"quality_score": 1.0}])

    def test_datasheet_table_cells_are_not_headings(self):
        self.assertFalse(self.chunker.is_heading("330.0"))
        self.assertFalse(self.chunker.is_heading("V"))
        self.assertFalse(self.chunker.is_heading("NIPDAU | SN"))
        self.assertFalse(self.chunker.is_heading("SPQ L (mm) W (mm) T (µm) B (mm)"))
        self.assertTrue(self.chunker.is_heading("Pin Configuration and Functions"))

    def test_numeric_table_fragments_are_removed_before_chunking(self):
        text = """
        12.4 6.4 5.2 2.1 8.0 12.0
        SPQ L (mm) W (mm) T (µm) B (mm)
        Pin Configuration and Functions
        The trigger pin starts the timing interval and the threshold pin stops it.
        """

        chunks, meta = self.chunker.smart_chunk_text(text, "ne555.pdf")

        joined = "\n".join(chunks)
        self.assertNotIn("12.4 6.4", joined)
        self.assertNotIn("SPQ L", joined)
        self.assertEqual(meta[0]["section"], "Pin Configuration and Functions")

    def test_short_electronics_labels_are_not_treated_as_package_noise(self):
        text = """
        Pin labels
        VCC GND
        LED
        OUT
        """

        cleaned = self.chunker.normalize_extracted_text(text)

        self.assertIn("VCC GND", cleaned)
        self.assertIn("LED", cleaned)
        self.assertIn("OUT", cleaned)

    def test_package_outline_chunks_are_marked_low_value(self):
        meta = self.chunker.make_chunk_meta(
            ".228-.244 TYP [5.80-6.19] [1.75] [1.27] 8X .012-.020",
            "ne555.pdf",
            "PACKAGE OUTLINE",
            "table",
        )

        self.assertEqual(meta["quality_score"], 0.0)
        self.assertIn("low_value_chunk", meta["quality_flags"])

    def test_package_named_useful_pin_text_is_kept(self):
        meta = self.chunker.make_chunk_meta(
            "The VCC pin supplies the timer package and the GND pin connects to ground.",
            "ne555.pdf",
            "Pin Configuration and Functions",
            "paragraph",
        )

        self.assertGreater(meta["quality_score"], 0.0)

    def test_ocr_quality_drops_short_text_without_electronics_signal(self):
        score, reason = self.chunker.evaluate_ocr_quality("3-Jun-2022", 95.0)

        self.assertLess(score, self.config["OCR_TXT_DROP_SCORE"])
        self.assertIn("isolated OCR noise", reason)

    def test_ocr_quality_keeps_short_wiring_text(self):
        score, reason = self.chunker.evaluate_ocr_quality("LED1(A) => J27 LED1(K) => GND", 85.0)

        self.assertGreaterEqual(score, self.config["OCR_TXT_DROP_SCORE"])
        self.assertNotIn("short text without electronics signal", reason)

    def test_ocr_quality_drops_low_content_high_confidence_text(self):
        score, reason = self.chunker.evaluate_ocr_quality("Main Label", 99.0)

        self.assertLess(score, self.config["OCR_TXT_DROP_SCORE"])
        self.assertIn("short text without electronics signal", reason)

    def test_ocr_quality_drops_generic_reflection_prompt(self):
        score, reason = self.chunker.evaluate_ocr_quality(
            "Think of ways you could apply this knowledge to solve your immediate problem and for innovations.",
            95.0,
        )

        self.assertLess(score, self.config["OCR_TXT_DROP_SCORE"])
        self.assertEqual(reason, "Empty")


if __name__ == "__main__":
    unittest.main()
