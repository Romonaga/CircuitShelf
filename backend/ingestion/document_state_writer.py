from __future__ import annotations

import os
import re
from typing import Any

from backend.ingestion.models import ExtractedDocument, ImageAsset
from backend.ingestion.ocr_assets import OcrAssetProcessor
from backend.ingestion.pdf_visuals import link_chunks_to_rendered_pages


class DocumentStateWriter:
    def __init__(self, *, config: Any, trace_logger):
        self.config = config
        self.trace_logger = trace_logger

    def store_extracted_document(self, document: ExtractedDocument, target_state, chunker, token_utils) -> None:
        page_texts = [page.text for page in document.pages]
        density = token_utils.estimate_token_density("\n\n".join(page_texts))
        if density > 40:
            self.trace_logger.warning(f"High token density in {document.source_path}: {density:.2f} tokens/line")

        chunks, metadata = chunker.smart_chunk_pages(page_texts, document.source_path)
        profile_meta = document.profile.metadata() if document.profile else {}
        for meta in metadata:
            meta.update(profile_meta)
            meta["parent_source"] = document.source_path

        self._link_page_visuals(document, chunks, metadata)
        image_chunks, image_sources, image_meta = self._store_image_assets(document, target_state, chunker, profile_meta)

        target_state.extend_chunks(
            chunks + image_chunks,
            [document.source_path] * len(chunks) + image_sources,
            metadata + image_meta,
        )

    def _link_page_visuals(self, document: ExtractedDocument, chunks: list[str], metadata: list[dict]) -> None:
        rendered_image_pages = {
            asset.page_number: asset.image_key
            for asset in document.assets
            if asset.source_kind == "rendered" and asset.page_number
        }
        linked_visuals = link_chunks_to_rendered_pages(
            chunks,
            metadata,
            document.source_path,
            {asset.image_key for asset in document.assets},
        )
        for meta in metadata:
            page = optional_int(meta.get("page"))
            if page in rendered_image_pages and not meta.get("source_image_id") and chunk_mentions_visual(meta):
                meta["source_image_id"] = rendered_image_pages[page]
        if linked_visuals:
            self.trace_logger.info(
                f"Linked {linked_visuals} text chunks to rendered page images for {os.path.basename(document.source_path)}"
            )

    def _store_image_assets(
        self,
        document: ExtractedDocument,
        target_state,
        chunker,
        profile_meta: dict,
    ) -> tuple[list[str], list[str], list[dict]]:
        image_chunks, image_sources, image_meta = [], [], []
        min_chars = int(self.config.get("OCR_INDEX_TEXT_MIN_CHARS", 80) or 80)
        for asset in document.assets:
            target_state.add_image_store(asset.image_key, OcrAssetProcessor.base64_image(asset.image_bytes))
            target_state.add_image_caption(asset.image_key, asset.caption)
            target_state.add_image_mime_type(asset.image_key, asset.mime_type)
            if asset.searchable_text:
                target_state.add_image_page_text(asset.image_key, asset.searchable_text)
            if self.config.get("INDEX_IMAGE_OCR_AS_TEXT", False) and asset.ocr_text and len(asset.ocr_text) >= min_chars:
                image_chunks.append(asset.ocr_text)
                image_sources.append(document.source_path)
                image_meta.append(self._ocr_chunk_meta(document, asset, chunker, profile_meta))
        return image_chunks, image_sources, image_meta

    def _ocr_chunk_meta(self, document: ExtractedDocument, asset: ImageAsset, chunker, profile_meta: dict) -> dict:
        ocr_meta = chunker.make_chunk_meta(asset.ocr_text, document.source_path, ocr_section(asset), "ocr")
        ocr_meta.update(profile_meta)
        ocr_meta.update({
            "page": asset.page_number,
            "parent_source": document.source_path,
            "source_image_id": asset.image_key,
            "ocr_score": asset.ocr_score,
            "ocr_confidence": asset.ocr_confidence,
            "chunk_type": "ocr",
        })
        return ocr_meta


def ocr_section(asset: ImageAsset) -> str:
    return "Rendered Page OCR" if asset.source_kind == "rendered" else "Image OCR"


def optional_int(value) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def chunk_mentions_visual(meta: dict) -> bool:
    text = " ".join(str(meta.get(key) or "") for key in ("section", "category", "chunk_type", "visual_references"))
    return bool(re.search(r"\b(fig(?:ure)?|diagram|schematic|pinout|layout|image|rendered|ocr)\b", text, re.IGNORECASE))
