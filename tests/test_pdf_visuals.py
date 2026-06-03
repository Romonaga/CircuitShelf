import os
import tempfile
import unittest
from io import BytesIO

import fitz
from PIL import Image

from pdf_visuals import (
    link_chunks_to_rendered_pages,
    page_image_coverage,
    render_pdf_visual_pages,
    rendered_page_image_key,
    should_render_visual_page,
    visual_references,
)


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

    def test_visual_page_detection_allows_raster_pages_with_signal(self):
        render, hits = should_render_visual_page(
            text="Circuit diagram with transistor wiring",
            drawing_count=0,
            image_count=2,
            min_drawings=100,
            raster_coverage=1.0,
            render_raster_pages=True,
            min_raster_coverage=0.8,
        )

        self.assertTrue(render)
        self.assertIn("diagram", hits)
        self.assertIn("circuit", hits)

    def test_visual_page_detection_skips_raster_pages_without_signal(self):
        render, _ = should_render_visual_page(
            text="Distributed by example vendor",
            drawing_count=0,
            image_count=2,
            min_drawings=100,
            raster_coverage=1.0,
            render_raster_pages=True,
            min_raster_coverage=0.8,
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

    def test_render_pdf_visual_pages_outputs_raster_page_png(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "scanned.pdf")
            image = Image.new("RGB", (300, 300), color="white")
            image_bytes = BytesIO()
            image.save(image_bytes, format="PNG")

            doc = fitz.open()
            page = doc.new_page(width=300, height=300)
            page.insert_image(page.rect, stream=image_bytes.getvalue())
            page.insert_text((20, 25), "Circuit diagram for transistor wiring")
            doc.save(path)
            doc.close()

            rendered = render_pdf_visual_pages(
                path,
                min_drawings=100,
                max_pages=2,
                zoom=1.0,
                render_raster_pages=True,
                min_raster_coverage=0.8,
            )

        self.assertEqual(len(rendered), 1)
        self.assertEqual(rendered[0].image_key, "scanned.pdf_page1_render")
        self.assertEqual(rendered[0].page_number, 1)
        self.assertIn("Circuit diagram", rendered[0].searchable_text)
        self.assertTrue(rendered[0].image_bytes.startswith(b"\x89PNG"))

    def test_page_image_coverage_dedupes_repeated_xrefs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "repeated-image.pdf")
            image = Image.new("RGB", (100, 100), color="white")
            image_bytes = BytesIO()
            image.save(image_bytes, format="PNG")

            doc = fitz.open()
            page = doc.new_page(width=200, height=200)
            page.insert_image(fitz.Rect(0, 0, 100, 100), stream=image_bytes.getvalue())
            xref = page.get_images(full=True)[0][0]
            page.insert_image(fitz.Rect(100, 100, 200, 200), xref=xref)
            doc.save(path)
            doc.close()

            with fitz.open(path) as pdf:
                coverage = page_image_coverage(pdf[0])

        self.assertAlmostEqual(coverage, 0.5, delta=0.05)

    def test_visual_references_detects_figure_and_package_terms(self):
        references = visual_references("See Fig. 3 for the graph and Package Dimensions for pin layout.")

        self.assertEqual(references, ["Fig. 3", "graph", "Package Dimensions", "pin layout"])

    def test_link_chunks_to_rendered_pages_uses_same_page_render(self):
        chunks = [
            "Fig. 3 shows normalized CTR over LED current.",
            "Plain description with no visual reference.",
            "Package Dimensions define the pin spacing.",
        ]
        metadata = [
            {"page": 5, "section": "Typical Characteristics"},
            {"page": 5, "section": "Description"},
            {"page": 8, "section": "Untitled Section"},
        ]
        available = {
            rendered_page_image_key("training/4n35.pdf", 5),
            rendered_page_image_key("training/4n35.pdf", 8),
        }

        linked = link_chunks_to_rendered_pages(chunks, metadata, "training/4n35.pdf", available)

        self.assertEqual(linked, 2)
        self.assertEqual(metadata[0]["source_image_id"], "4n35.pdf_page5_render")
        self.assertNotIn("source_image_id", metadata[1])
        self.assertEqual(metadata[2]["source_image_id"], "4n35.pdf_page8_render")


if __name__ == "__main__":
    unittest.main()
