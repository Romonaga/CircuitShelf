import os

import pytesseract


def configure_tesseract(*, config, trace_logger) -> None:
    if os.name == "nt":
        trace_logger.info("We are on Windows, Set the tesseract_cmd")
        pytesseract.pytesseract.tesseract_cmd = os.environ.get(
            "CIRCUITSHELF_TESSERACT_CMD",
            r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe",
        )
