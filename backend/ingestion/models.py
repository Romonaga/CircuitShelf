from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DocumentProfile:
    document_type: str
    confidence: float
    component_name: str = ""
    component_type: str = ""
    reasons: tuple[str, ...] = ()
    negative_signals: tuple[str, ...] = ()

    @property
    def is_component_datasheet(self) -> bool:
        return self.document_type == "component_datasheet" and bool(self.component_name)

    def metadata(self) -> dict:
        return {
            "document_type": self.document_type,
            "document_profile_confidence": self.confidence,
            "component_name": self.component_name,
            "component_type": self.component_type,
            "document_profile_reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class ExtractedPage:
    page_number: int
    text: str


@dataclass(frozen=True)
class ImageAsset:
    image_key: str
    page_number: int | None
    caption: str
    image_bytes: bytes
    mime_type: str = "image/png"
    searchable_text: str = ""
    ocr_text: str = ""
    ocr_score: float = 0.0
    ocr_confidence: float | None = None
    source_kind: str = "embedded"


@dataclass
class ExtractedDocument:
    source_path: str
    pages: list[ExtractedPage] = field(default_factory=list)
    assets: list[ImageAsset] = field(default_factory=list)
    profile: DocumentProfile | None = None

    @property
    def text_sample(self) -> str:
        return "\n".join(page.text for page in self.pages if page.text).strip()
