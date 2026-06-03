from __future__ import annotations

from io import BytesIO

import pypdfium2 as pdfium


class PdfiumPageRenderer:
    """Render PDF pages through PDFium instead of PyMuPDF."""

    def __init__(self, *, scale: float = 1.5, trace_logger=None):
        self.scale = float(scale or 1.5)
        self.trace_logger = trace_logger

    def render_pages(self, path: str, page_numbers: list[int]) -> dict[int, bytes]:
        if not page_numbers:
            return {}
        rendered: dict[int, bytes] = {}
        try:
            pdf = pdfium.PdfDocument(path)
        except Exception as exc:
            if self.trace_logger:
                self.trace_logger.warning(f"PDFium could not open {path}; continuing with text-only extraction: {exc}")
            return rendered
        try:
            page_count = len(pdf)
            for page_number in page_numbers:
                if page_number < 1 or page_number > page_count:
                    continue
                page = None
                try:
                    page = pdf[page_number - 1]
                    bitmap = page.render(scale=self.scale)
                    image = bitmap.to_pil()
                    output = BytesIO()
                    image.save(output, format="PNG")
                    rendered[page_number] = output.getvalue()
                except Exception as exc:
                    if self.trace_logger:
                        self.trace_logger.warning(f"PDFium render failed on page {page_number}: {exc}")
                finally:
                    try:
                        if page is not None:
                            page.close()
                    except Exception:
                        pass
        finally:
            try:
                pdf.close()
            except Exception:
                pass
        return rendered
