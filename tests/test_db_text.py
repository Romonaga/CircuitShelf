import unittest

from db.text import clean_db_text


class DbTextTests(unittest.TestCase):
    def test_removes_nul_bytes_from_extracted_pdf_text(self):
        self.assertEqual(clean_db_text("op\x00amp\x00 text"), "opamp text")

    def test_preserves_none_default(self):
        self.assertIsNone(clean_db_text(None, None))
        self.assertEqual(clean_db_text(None), "")


if __name__ == "__main__":
    unittest.main()
