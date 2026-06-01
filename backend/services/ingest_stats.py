from typing import Callable


def file_changes_payload(changes):
    if not changes:
        return None
    return {
        "added": len(changes.added),
        "modified": len(changes.modified),
        "removed": len(changes.removed),
        "unchanged": len(changes.unchanged),
        "addedFiles": changes.added[:20],
        "modifiedFiles": changes.modified[:20],
        "removedFiles": changes.removed[:20],
        "unchangedFiles": changes.unchanged[:20],
    }


def count_state_chunks_by_document(target_state, *, vector_store) -> dict[str, int]:
    counts = {}
    sources = target_state.get_sources()
    metadata = target_state.get_metadata()
    for idx, source in enumerate(sources):
        meta = metadata[idx] if idx < len(metadata) else {}
        rel_path = vector_store.rel_path_for_source(source, meta)
        counts[rel_path] = counts.get(rel_path, 0) + 1
    return counts


def count_state_images_by_document(
    image_keys,
    rel_paths,
    *,
    image_asset_belongs_to_document: Callable[[str, str], bool],
) -> dict[str, int]:
    counts = {rel_path: 0 for rel_path in rel_paths}
    for image_id in image_keys:
        for rel_path in rel_paths:
            if image_asset_belongs_to_document(image_id, rel_path):
                counts[rel_path] += 1
                break
    return counts


def collect_document_ingest_stats(
    target_state,
    rel_paths,
    *,
    vector_store,
    image_asset_belongs_to_document: Callable[[str, str], bool],
    raw_chunk_counts=None,
    raw_image_counts=None,
    raw_ocr_image_counts=None,
) -> dict[str, dict]:
    rel_paths = list(rel_paths or [])
    kept_chunk_counts = count_state_chunks_by_document(target_state, vector_store=vector_store)
    indexed_image_counts = count_state_images_by_document(
        target_state.get_image_id_list(),
        rel_paths,
        image_asset_belongs_to_document=image_asset_belongs_to_document,
    )
    raw_chunk_counts = raw_chunk_counts or {}
    raw_image_counts = raw_image_counts or count_state_images_by_document(
        target_state.get_image_store().keys(),
        rel_paths,
        image_asset_belongs_to_document=image_asset_belongs_to_document,
    )
    raw_ocr_image_counts = raw_ocr_image_counts or count_state_images_by_document(
        target_state.get_image_page_text().keys(),
        rel_paths,
        image_asset_belongs_to_document=image_asset_belongs_to_document,
    )

    stats = {}
    for rel_path in rel_paths:
        raw_chunks = int(raw_chunk_counts.get(rel_path, 0) or 0)
        kept_chunks = int(kept_chunk_counts.get(rel_path, 0) or 0)
        stats[rel_path] = {
            "rawChunkCount": raw_chunks,
            "chunkCount": kept_chunks,
            "droppedChunkCount": max(raw_chunks - kept_chunks, 0),
            "extractedImageCount": int(raw_image_counts.get(rel_path, 0) or 0),
            "indexedImageTextCount": int(indexed_image_counts.get(rel_path, 0) or 0),
            "ocrImageTextCount": int(raw_ocr_image_counts.get(rel_path, 0) or 0),
        }
    return stats


def summarize_document_ingest_stats(document_stats) -> dict:
    values = list((document_stats or {}).values())
    return {
        "documents": len(values),
        "rawChunks": sum(item.get("rawChunkCount", 0) for item in values),
        "chunks": sum(item.get("chunkCount", 0) for item in values),
        "droppedChunks": sum(item.get("droppedChunkCount", 0) for item in values),
        "extractedImages": sum(item.get("extractedImageCount", 0) for item in values),
        "indexedImageTexts": sum(item.get("indexedImageTextCount", 0) for item in values),
        "ocrImageTexts": sum(item.get("ocrImageTextCount", 0) for item in values),
    }
