from io import BytesIO

import fitz
from PIL import Image

from backend.ingestion.pdf.embedded_image_extractor import EmbeddedPdfImageExtractor


def _png_bytes(width: int, height: int, color: str = "white") -> bytes:
    image = Image.new("RGB", (width, height), color)
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def test_embedded_pdf_images_are_extracted_with_page_numbers(tmp_path):
    pdf_path = tmp_path / "lesson.pdf"
    document = fitz.open()
    try:
        page_one = document.new_page(width=300, height=300)
        page_one.insert_image(fitz.Rect(30, 30, 230, 180), stream=_png_bytes(200, 150, "red"))

        page_two = document.new_page(width=300, height=300)
        page_two.insert_image(fitz.Rect(20, 20, 35, 35), stream=_png_bytes(15, 15, "blue"))
        page_two.insert_image(fitz.Rect(40, 40, 260, 240), stream=_png_bytes(220, 200, "green"))

        document.save(pdf_path)
    finally:
        document.close()

    result = EmbeddedPdfImageExtractor(
        config={
            "OCR_MIN_IMAGE_WIDTH": 20,
            "OCR_MIN_IMAGE_HEIGHT": 20,
            "OCR_MIN_IMAGE_AREA": 900,
            "PDF_EMBEDDED_IMAGE_OCR_MIN_WIDTH": 80,
            "PDF_EMBEDDED_IMAGE_OCR_MIN_HEIGHT": 80,
            "PDF_EMBEDDED_IMAGE_OCR_MIN_AREA": 6400,
        }
    ).extract(str(pdf_path))

    assert [(image.page_number, image.width, image.height) for image in result.images] == [
        (1, 200, 150),
        (2, 220, 200),
    ]
    assert result.skipped_tiny == 1
    assert result.failed == 0
