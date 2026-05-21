import unittest

from db.image_store import ImageStore
from ingest_manifest import FileRecord


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


if __name__ == "__main__":
    unittest.main()
