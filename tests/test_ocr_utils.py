import unittest

from PIL import Image

from ocr_utils import should_skip_image


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


if __name__ == "__main__":
    unittest.main()
