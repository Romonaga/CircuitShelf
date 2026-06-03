from __future__ import annotations

from backend.ingestion.pdf.extractor import PdfDocumentExtractor


class PdfExtractor(PdfDocumentExtractor):
    """Compatibility alias for older imports.

    The active PDF pipeline lives in backend.ingestion.pdf and no longer uses
    PyMuPDF for extraction/rendering.
    """

