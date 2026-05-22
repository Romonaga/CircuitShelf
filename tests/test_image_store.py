import unittest
from io import BytesIO

from db.image_store import ImageStore
from ingest_manifest import FileRecord
from PIL import Image


class ImageStoreHelperTests(unittest.TestCase):
    def test_resolves_pdf_image_key_to_source_document_and_page(self):
        store = ImageStore(None, "training")
        file_records = {"books/ne555.pdf": FileRecord("books/ne555.pdf", 100, 10)}
        documents = {"books/ne555.pdf": {"display_name": "ne555.pdf"}}

        rel_path, page, score, confidence = store._resolve_image_document(
            "ne555.pdf_page7_img2",
            {},
            file_records,
            documents,
        )

        self.assertEqual(rel_path, "books/ne555.pdf")
        self.assertEqual(page, 7)
        self.assertIsNone(score)
        self.assertIsNone(confidence)

    def test_metadata_source_takes_priority(self):
        store = ImageStore(None, "training")
        rel_path, page, score, confidence = store._resolve_image_document(
            "custom-key",
            {
                "parent_source": "training/books/ne556.pdf",
                "page": "4",
                "ocr_score": "0.87",
                "ocr_confidence": "92.5",
            },
            {"books/ne556.pdf": FileRecord("books/ne556.pdf", 100, 10)},
            {"books/ne556.pdf": {"display_name": "ne556.pdf"}},
        )

        self.assertEqual(rel_path, "books/ne556.pdf")
        self.assertEqual(page, 4)
        self.assertEqual(score, 0.87)
        self.assertEqual(confidence, 92.5)

    def test_prepares_large_image_as_smaller_webp(self):
        store = ImageStore(None, "training")
        image = Image.effect_noise((300, 300), 80).convert("RGB")
        raw = BytesIO()
        image.save(raw, format="PNG")

        stored_bytes, mime_type, width, height = store._prepare_image_for_storage(raw.getvalue())

        self.assertEqual((width, height), (300, 300))
        self.assertEqual(mime_type, "image/webp")
        self.assertLess(len(stored_bytes), len(raw.getvalue()))

    def test_keeps_original_when_webp_is_not_smaller(self):
        store = ImageStore(None, "training")
        image = Image.effect_noise((100, 100), 80).convert("RGB")
        raw = BytesIO()
        image.save(raw, format="JPEG", quality=60)

        stored_bytes, mime_type, width, height = store._prepare_image_for_storage(raw.getvalue())

        self.assertEqual((width, height), (100, 100))
        self.assertEqual(mime_type, "image/jpeg")
        self.assertEqual(stored_bytes, raw.getvalue())


if __name__ == "__main__":
    unittest.main()
