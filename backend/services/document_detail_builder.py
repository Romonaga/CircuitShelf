from __future__ import annotations

from collections import OrderedDict
from typing import Any, Callable

from backend.ingestion.tokenize_util import TokenUtils


class DocumentDetailBuilder:
    def __init__(
        self,
        *,
        state: Any,
        vector_store: Any,
        image_asset_belongs_to_document: Callable[[str, str], bool],
        extract_page_number: Callable[[str], int | None],
        document_source_from_metadata: Callable[[str, dict], str],
        source_image_id_from_metadata: Callable[[str, dict], str | None],
        extract_pinout_map: Callable[[list, list, str], dict],
        get_or_build_datasheet_intelligence: Callable[..., dict],
        display_source_name: Callable[[str], str],
    ):
        self.state = state
        self.vector_store = vector_store
        self.image_asset_belongs_to_document = image_asset_belongs_to_document
        self.extract_page_number = extract_page_number
        self.document_source_from_metadata = document_source_from_metadata
        self.source_image_id_from_metadata = source_image_id_from_metadata
        self.extract_pinout_map = extract_pinout_map
        self.get_or_build_datasheet_intelligence = get_or_build_datasheet_intelligence
        self.display_source_name = display_source_name

    def build(self, doc_name: str) -> dict:
        rows = []
        pages = OrderedDict()
        image_assets = []
        chunks = self.state.get_chunks()
        metadata = self.state.get_metadata()
        sources = self.state.get_sources()
        image_store_payload = self.state.get_image_store()
        image_captions = self.state.get_image_captions()
        image_text = self.state.get_image_page_text()
        image_mime_types = self.state.get_image_mime_types()
        intelligence_chunks = []
        intelligence_metadata = []

        for image_id, image_base64 in sorted(image_store_payload.items()):
            if not self.image_asset_belongs_to_document(image_id, doc_name):
                continue
            page = self.extract_page_number(image_id) or None
            image_payload = {
                "imageKey": image_id,
                "caption": image_captions.get(image_id, image_id),
                "page": page,
                "imageMimeType": image_mime_types.get(image_id, "image/png"),
                "imageBase64": image_base64,
                "ocrText": image_text.get(image_id, ""),
            }
            image_assets.append(image_payload)
            if page is not None:
                pages.setdefault(page, {"page": page, "chunks": [], "images": []})["images"].append(image_payload)

        for idx, source in enumerate(sources):
            meta = metadata[idx] if idx < len(metadata) else {}
            doc_source = self.document_source_from_metadata(source, meta)
            if doc_source != doc_name:
                continue
            text = chunks[idx] if idx < len(chunks) else ""
            intelligence_chunks.append(text)
            intelligence_metadata.append({**meta, "source": doc_name, "parent_source": doc_name})
            row = {
                "index": idx,
                "section": meta.get("section", "Unknown"),
                "category": meta.get("category", "Uncategorized"),
                "page": meta.get("page"),
                "sourceImageId": self.source_image_id_from_metadata(source, meta),
                "tokens": TokenUtils.tokenize_len(text),
                "preview": text[:500],
            }
            rows.append(row)
            page = row["page"]
            if page is not None:
                pages.setdefault(page, {"page": page, "chunks": [], "images": []})["chunks"].append(row)

        pinout_chunks = list(intelligence_chunks)
        pinout_metadata = list(intelligence_metadata)
        for image in image_assets:
            if image.get("ocrText"):
                pinout_chunks.append(image["ocrText"])
                pinout_metadata.append({
                    "source": doc_name,
                    "parent_source": doc_name,
                    "page": image.get("page"),
                    "source_image_id": image.get("imageKey"),
                    "section": "Image OCR",
                    "category": "ocr",
                })
        pinout = self.extract_pinout_map(pinout_chunks, pinout_metadata, doc_name)
        intelligence = self.get_or_build_datasheet_intelligence(doc_name, pinout_chunks, pinout_metadata)
        return {
            "document": doc_name,
            "displayName": self.display_source_name(doc_name),
            "chunks": rows,
            "images": image_assets,
            "pages": sorted(pages.values(), key=lambda item: int(item["page"])),
            "ingestStats": self._ingest_stats(doc_name),
            "pinout": intelligence.get("pinout") if intelligence.get("pinout", {}).get("pins") else pinout,
            "intelligence": intelligence,
        }

    def _ingest_stats(self, doc_name: str) -> dict | None:
        return next(
            (
                {
                    "rawChunkCount": int(row["raw_chunk_count"] or 0),
                    "chunkCount": int(row["actual_chunk_count"] or row["chunk_count"] or 0),
                    "droppedChunkCount": int(row["dropped_chunk_count"] or 0),
                    "extractedImageCount": int(row["extracted_image_count"] or 0),
                    "storedImageCount": int(row["stored_image_count"] or 0),
                    "indexedImageTextCount": int(row["indexed_image_text_count"] or 0),
                    "ocrImageTextCount": int(row["ocr_image_text_count"] or 0),
                }
                for row in self.vector_store.list_document_stats()
                if row["source_path"] == doc_name
            ),
            None,
        )
