import os
import tempfile
import unittest

import fitz

from pdf_visuals import render_pdf_visual_pages, should_render_visual_page


class PdfVisualTests(unittest.TestCase):
    def test_visual_page_detection_requires_signal(self):
        render, hits = should_render_visual_page(
            text="Package Dimensions and pin layout",
            drawing_count=120,
            image_count=0,
            min_drawings=100,
        )

        self.assertTrue(render)
        self.assertIn("pin", hits)
        self.assertIn("package", hits)

    def test_visual_page_detection_allows_dense_vectors(self):
        render, hits = should_render_visual_page(
            text="",
            drawing_count=250,
            image_count=0,
            min_drawings=100,
        )

        self.assertTrue(render)
        self.assertEqual(hits, [])

    def test_visual_page_detection_skips_low_signal_vector_pages(self):
        render, _ = should_render_visual_page(
            text="Distributed by example vendor",
            drawing_count=120,
            image_count=0,
            min_drawings=100,
        )

        self.assertFalse(render)

    def test_render_pdf_visual_pages_outputs_png(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "pinout.pdf")
            doc = fitz.open()
            page = doc.new_page(width=200, height=200)
            page.insert_text((20, 25), "Package Dimensions pinout diagram")
            for offset in range(0, 120, 3):
                page.draw_line((20, 50 + offset), (180, 50 + offset))
            doc.save(path)
            doc.close()

            rendered = render_pdf_visual_pages(path, min_drawings=10, max_pages=2, zoom=1.0)

        self.assertEqual(len(rendered), 1)
        self.assertEqual(rendered[0].image_key, "pinout.pdf_page1_render")
        self.assertEqual(rendered[0].page_number, 1)
        self.assertIn("Package Dimensions", rendered[0].searchable_text)
        self.assertTrue(rendered[0].image_bytes.startswith(b"\x89PNG"))


if __name__ == "__main__":
    unittest.main()
