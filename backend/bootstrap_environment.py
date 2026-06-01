import os

import nltk
import pytesseract


def configure_nltk_and_tesseract(*, config, trace_logger) -> None:
    if config.get("BYPASS_NLTK_DOWNLOAD", True):
        nltk_data_dir = config.get("NLTK_DATA_DIR")
        if os.path.exists(nltk_data_dir):
            trace_logger.info(f"NLTK_DATA_DIR '{nltk_data_dir}' exists. Using it for NLTK data.")
            if nltk_data_dir not in nltk.data.path:
                nltk.data.path.insert(0, nltk_data_dir)
            nltk.download = lambda *args, **kwargs: (_ for _ in ()).throw(
                RuntimeError("Downloading NLTK data is disabled in production.")
            )
        else:
            trace_logger.warning(f"NLTK_DATA_DIR '{nltk_data_dir}' does not exist. Please check falling back to Local.")

    if os.name == "nt":
        trace_logger.info("We are on Windows, Set the tesseract_cmd")
        pytesseract.pytesseract.tesseract_cmd = config.get(
            "TESSERACT_CMD",
            r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe",
        )
