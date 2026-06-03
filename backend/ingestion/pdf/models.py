from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PdfTable:
    page_number: int
    rows: list[list[str]]

    @property
    def text(self) -> str:
        rendered_rows = []
        for row in self.rows:
            cells = [str(cell or "").strip() for cell in row]
            if any(cells):
                rendered_rows.append(" | ".join(cells))
        return "\n".join(rendered_rows)


@dataclass
class PdfPageExtraction:
    page_number: int
    text: str = ""
    tables: list[PdfTable] = field(default_factory=list)
    image_count: int = 0
    drawing_count: int = 0
    raster_coverage: float = 0.0
    width: float = 0.0
    height: float = 0.0

    @property
    def searchable_text(self) -> str:
        table_text = "\n\n".join(table.text for table in self.tables if table.text)
        return "\n\n".join(part for part in [self.text.strip(), table_text.strip()] if part).strip()

    @property
    def native_char_count(self) -> int:
        return len((self.text or "").strip())


@dataclass(frozen=True)
class PdfRenderRequest:
    order: int
    page_number: int
    image_key: str
    reason: str
