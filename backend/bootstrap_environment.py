import os

import nltk
import pytesseract


def configure_nltk_and_tesseract(*, config, trace_logger) -> None:
    _configure_nltk(trace_logger)

    if os.name == "nt":
        trace_logger.info("We are on Windows, Set the tesseract_cmd")
        pytesseract.pytesseract.tesseract_cmd = config.get(
            "TESSERACT_CMD",
            r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe",
        )


def _configure_nltk(trace_logger) -> None:
    env_dir = os.environ.get("NLTK_DATA_DIR") or os.environ.get("NLTK_DATA")
    candidate_dirs = [
        env_dir,
        os.path.join(os.getcwd(), "data", "nltk_data"),
        os.path.join(os.getcwd(), "nltk_data"),
        os.path.join(os.getcwd(), ".venv", "nltk_data"),
        os.path.join(os.getcwd(), ".venv", "share", "nltk_data"),
    ]
    for candidate in candidate_dirs:
        if candidate and os.path.isdir(candidate) and candidate not in nltk.data.path:
            nltk.data.path.insert(0, candidate)

    nltk.download = lambda *args, **kwargs: (_ for _ in ()).throw(
        RuntimeError("CircuitShelf does not download NLTK data at runtime. Install NLTK data with the app package.")
    )

    for resource in ("tokenizers/punkt_tab", "tokenizers/punkt"):
        try:
            found = nltk.data.find(resource)
            trace_logger.info(f"NLTK resource available: {resource} at {found}.")
            return
        except LookupError:
            continue
    trace_logger.warning("NLTK sentence tokenizer data was not found. CircuitShelf will use its built-in fallback splitter.")
