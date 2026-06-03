from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Iterator


_MUPDF_LOCK = threading.RLock()


@contextmanager
def mupdf_native_section() -> Iterator[None]:
    """Guard PyMuPDF/MuPDF calls that are unsafe under heavy thread concurrency."""
    with _MUPDF_LOCK:
        yield
