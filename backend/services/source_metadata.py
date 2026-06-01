import os
import re
from collections import OrderedDict
from typing import Any

import numpy as np


def document_source_from_metadata(source: str, metadata: dict | None = None) -> str:
    metadata = metadata or {}
    return metadata.get("parent_source") or metadata.get("source") or source


def display_source_name(source: str | None) -> str:
    return os.path.basename(source) if source else "Unknown"


def source_image_id_from_metadata(source: str, metadata: dict | None = None) -> str | None:
    metadata = metadata or {}
    if metadata.get("source_image_id"):
        return metadata["source_image_id"]

    candidate = metadata.get("source") or source
    if not candidate:
        return None

    candidate_base = os.path.basename(candidate)
    parent_base = os.path.basename(metadata.get("parent_source") or "")
    if parent_base and candidate_base.startswith(f"{parent_base}_page"):
        return candidate
    if "_page" in candidate_base and "_img" in candidate_base:
        return candidate
    return None


def image_asset_belongs_to_document(image_id: str, doc_source: str | None) -> bool:
    doc_base = os.path.basename(doc_source or "")
    if not doc_base:
        return False
    return (
        image_id == doc_base
        or image_id.startswith(f"{doc_base}_page")
        or image_id.startswith(f"{doc_base}_textbox")
    )


def normalize_sources_for_api(sources: Any) -> list:
    if isinstance(sources, str):
        return [source for source in sources.splitlines() if source.strip()]
    if isinstance(sources, (list, tuple, set)):
        return list(sources)
    return []


def api_scalar(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    return value


def build_source_payload(selected_chunks: list[dict]) -> list[dict]:
    grouped = OrderedDict()
    for chunk in selected_chunks:
        source = chunk.get("source") or "Unknown"
        doc = grouped.setdefault(
            source,
            {
                "source": source,
                "displayName": display_source_name(source),
                "pages": [],
                "chunkCount": 0,
                "chunks": [],
            },
        )
        page = api_scalar(chunk.get("page"))
        if page is not None and page not in doc["pages"]:
            doc["pages"].append(page)

        text = chunk.get("text", "")
        preview = re.sub(r"\s+", " ", text).strip()
        if len(preview) > 360:
            preview = f"{preview[:360].rstrip()}..."

        doc["chunkCount"] += 1
        doc["chunks"].append({
            "index": api_scalar(chunk.get("index")),
            "page": page,
            "section": chunk.get("section", "Unknown"),
            "category": chunk.get("category", "Uncategorized"),
            "distance": api_scalar(chunk.get("distance")),
            "sourceImageId": chunk.get("source_image_id"),
            "preview": preview,
        })

    for doc in grouped.values():
        doc["pages"] = sorted(doc["pages"], key=lambda item: (not isinstance(item, (int, float)), item))
    return list(grouped.values())
