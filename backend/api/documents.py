from __future__ import annotations

import os
import uuid
from collections import OrderedDict
from typing import Any

from fastapi import APIRouter, File, Query, Request, UploadFile
from fastapi.responses import JSONResponse

from tokenize_util import TokenUtils
from backend.api.dependencies import ApiDependencies


def safe_upload_filename(filename: str, supported_extensions: set[str]) -> str:
    name = os.path.basename(str(filename or "")).strip()
    if not name or name in {".", ".."}:
        raise ValueError("Upload must include a file name.")
    if name.startswith(".") or any(char in name for char in ("/", "\\")):
        raise ValueError("Upload file name is not allowed.")
    ext = os.path.splitext(name)[1].lower()
    if ext not in supported_extensions:
        allowed = ", ".join(sorted(supported_extensions))
        raise ValueError(f"Unsupported file type. Allowed: {allowed}")
    return name


async def write_uploaded_documents(files: list[UploadFile], overwrite: bool, training_dir: str, supported_extensions: set[str]) -> dict:
    if not files:
        raise ValueError("Upload must include at least one file.")

    os.makedirs(training_dir, exist_ok=True)
    training_root = os.path.abspath(training_dir)
    prepared = []
    seen_names = set()
    tmp_paths = []
    uploaded = []
    skipped = []

    try:
        for file in files:
            filename = safe_upload_filename(file.filename or "", supported_extensions)
            if filename in seen_names:
                skipped.append({"filename": filename, "reason": "duplicate selection"})
                continue
            seen_names.add(filename)

            destination = os.path.abspath(os.path.join(training_dir, filename))
            if not destination.startswith(training_root + os.sep):
                raise ValueError("Upload destination is outside the training directory.")
            if os.path.exists(destination) and not overwrite:
                skipped.append({"filename": filename, "reason": "already exists"})
                continue

            tmp_path = os.path.join(training_dir, f".{filename}.{uuid.uuid4().hex}.upload")
            prepared.append((file, filename, destination, tmp_path))
            tmp_paths.append(tmp_path)

        for file, filename, destination, tmp_path in prepared:
            bytes_written = 0
            with open(tmp_path, "wb") as out_file:
                while True:
                    chunk = await file.read(1024 * 1024)
                    if not chunk:
                        break
                    bytes_written += len(chunk)
                    out_file.write(chunk)
            if bytes_written <= 0:
                raise ValueError(f"Uploaded file was empty: {filename}")
            uploaded.append({
                "filename": filename,
                "destination": destination,
                "tmpPath": tmp_path,
                "bytes": bytes_written,
            })

        for item in uploaded:
            os.replace(item["tmpPath"], item["destination"])
        return {
            "uploaded": [{"filename": item["filename"], "bytes": item["bytes"]} for item in uploaded],
            "skipped": skipped,
        }
    except Exception:
        for tmp_path in tmp_paths:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        raise
    finally:
        for file in files:
            await file.close()


def create_router(
    deps: ApiDependencies,
    *,
    training_dir: str,
    supported_training_extensions: Callable[[], set[str]],
    vector_store: Any,
    image_store: Any,
    state: Any,
    trace_logger: Any,
    start_index_check: Callable[[str], dict],
    image_asset_belongs_to_document: Callable[[str, str], bool],
    extract_page_number: Callable[[str], int | None],
    document_source_from_metadata: Callable[[str, dict], str],
    source_image_id_from_metadata: Callable[[str, dict], str | None],
    extract_pinout_map: Callable[[list, list, str], dict],
    get_or_build_datasheet_intelligence: Callable[[str], dict],
    display_source_name: Callable[[str], str],
) -> APIRouter:
    router = APIRouter()

    def build_document_detail(doc_name: str) -> dict:
        rows = []
        pages = OrderedDict()
        image_assets = []
        chunks = state.get_chunks()
        metadata = state.get_metadata()
        sources = state.get_sources()
        image_store_payload = state.get_image_store()
        image_captions = state.get_image_captions()
        image_text = state.get_image_page_text()
        image_mime_types = state.get_image_mime_types()

        for image_id, image_base64 in sorted(image_store_payload.items()):
            if not image_asset_belongs_to_document(image_id, doc_name):
                continue
            page = extract_page_number(image_id) or None
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
            doc_source = document_source_from_metadata(source, meta)
            if doc_source != doc_name:
                continue
            text = chunks[idx] if idx < len(chunks) else ""
            row = {
                "index": idx,
                "section": meta.get("section", "Unknown"),
                "category": meta.get("category", "Uncategorized"),
                "page": meta.get("page"),
                "sourceImageId": source_image_id_from_metadata(source, meta),
                "tokens": TokenUtils.tokenize_len(text),
                "preview": text[:500],
            }
            rows.append(row)
            page = row["page"]
            if page is not None:
                pages.setdefault(page, {"page": page, "chunks": [], "images": []})["chunks"].append(row)

        pinout_chunks = list(chunks)
        pinout_metadata = list(metadata)
        for image in image_assets:
            if image.get("ocrText"):
                pinout_chunks.append(image["ocrText"])
                pinout_metadata.append({"source": doc_name, "page": image.get("page")})
        pinout = extract_pinout_map(pinout_chunks, pinout_metadata, doc_name)
        intelligence = get_or_build_datasheet_intelligence(doc_name)
        return {
            "document": doc_name,
            "displayName": display_source_name(doc_name),
            "chunks": rows,
            "images": image_assets,
            "pages": sorted(pages.values(), key=lambda item: int(item["page"])),
            "ingestStats": next(
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
                    for row in vector_store.list_document_stats()
                    if row["source_path"] == doc_name
                ),
                None,
            ),
            "pinout": intelligence.get("pinout") if intelligence.get("pinout", {}).get("pins") else pinout,
            "intelligence": intelligence,
        }

    @router.get("/api/documents")
    async def documents(req: Request, scope: str = Query("visible")):
        entity_id = None
        stats_scope = "visible"
        if scope == "global":
            _, error = deps.require_system_admin_user(req)
            if error:
                return error
            stats_scope = "global"
        else:
            _, entity, error = deps.require_entity_member(req)
            if error:
                return error
            entity_id = entity.entity_id
        docs = []
        for row in vector_store.list_document_stats(entity_id=entity_id, scope=stats_scope):
            docs.append({
                "source": row["source_path"],
                "displayName": row["display_name"],
                "chunkCount": int(row["actual_chunk_count"] or row["chunk_count"] or 0),
                "imageCount": int(row["actual_image_count"] or row["stored_image_count"] or 0),
                "rawChunkCount": int(row["raw_chunk_count"] or 0),
                "droppedChunkCount": int(row["dropped_chunk_count"] or 0),
                "extractedImageCount": int(row["extracted_image_count"] or 0),
                "storedImageCount": int(row["stored_image_count"] or 0),
                "indexedImageTextCount": int(row["indexed_image_text_count"] or 0),
                "ocrImageTextCount": int(row["ocr_image_text_count"] or 0),
            })
        return {"documents": docs}

    @router.post("/api/documents/upload")
    async def upload_document(
        req: Request,
        file: UploadFile = File(...),
        overwrite: bool = Query(False),
        scope: str = Query("entity"),
    ):
        entity_id = None
        created_by_user_id = None
        is_global = scope == "global"
        if is_global:
            user, error = deps.require_system_admin_user(req)
            if error:
                return error
            created_by_user_id = deps.user_id_for_user(user)
        else:
            user, entity, error = deps.require_entity_admin(req)
            if error:
                return error
            entity_id = entity.entity_id
            created_by_user_id = deps.user_id_for_user(user)

        try:
            upload_result = await write_uploaded_documents([file], overwrite, training_dir, supported_training_extensions())
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        except Exception as exc:
            trace_logger.error(f"❌ Document upload failed: {exc}")
            return JSONResponse({"error": str(exc)}, status_code=500)

        uploaded_files = upload_result["uploaded"]
        skipped_files = upload_result["skipped"]
        for item in uploaded_files:
            vector_store.set_ingest_scope(
                item["filename"],
                entity_id=entity_id,
                is_global=is_global,
                created_by_user_id=created_by_user_id,
            )
        filename = uploaded_files[0]["filename"] if uploaded_files else ""
        index_job = start_index_check(f"upload:{filename}") if uploaded_files else {"started": False}
        return {
            "ok": True,
            "filename": filename,
            "bytes": sum(item["bytes"] for item in uploaded_files),
            "files": uploaded_files,
            "skippedFiles": skipped_files,
            "count": len(uploaded_files),
            "skippedCount": len(skipped_files),
            "indexing": index_job,
        }

    @router.post("/api/documents/upload-batch")
    async def upload_documents(
        req: Request,
        files: list[UploadFile] = File(...),
        overwrite: bool = Query(False),
        scope: str = Query("entity"),
    ):
        entity_id = None
        created_by_user_id = None
        is_global = scope == "global"
        if is_global:
            user, error = deps.require_system_admin_user(req)
            if error:
                return error
            created_by_user_id = deps.user_id_for_user(user)
        else:
            user, entity, error = deps.require_entity_admin(req)
            if error:
                return error
            entity_id = entity.entity_id
            created_by_user_id = deps.user_id_for_user(user)

        try:
            upload_result = await write_uploaded_documents(files, overwrite, training_dir, supported_training_extensions())
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        except Exception as exc:
            trace_logger.error(f"❌ Batch document upload failed: {exc}")
            return JSONResponse({"error": str(exc)}, status_code=500)

        uploaded_files = upload_result["uploaded"]
        skipped_files = upload_result["skipped"]
        for item in uploaded_files:
            vector_store.set_ingest_scope(
                item["filename"],
                entity_id=entity_id,
                is_global=is_global,
                created_by_user_id=created_by_user_id,
            )
        reason = f"upload-batch:{len(uploaded_files)}"
        index_job = start_index_check(reason) if uploaded_files else {"started": False}
        return {
            "ok": True,
            "files": uploaded_files,
            "skippedFiles": skipped_files,
            "count": len(uploaded_files),
            "skippedCount": len(skipped_files),
            "bytes": sum(item["bytes"] for item in uploaded_files),
            "indexing": index_job,
        }

    @router.get("/api/document")
    async def document_detail_query(req: Request, source: str, scope: str = Query("visible")):
        entity_id = None
        stats_scope = "visible"
        if scope == "global":
            _, error = deps.require_system_admin_user(req)
            if error:
                return error
            stats_scope = "global"
        else:
            _, entity, error = deps.require_entity_member(req)
            if error:
                return error
            entity_id = entity.entity_id
        visible_sources = {
            row["source_path"]
            for row in vector_store.list_document_stats(entity_id=entity_id, scope=stats_scope)
        }
        if source not in visible_sources:
            return JSONResponse({"error": "Document not found."}, status_code=404)
        return build_document_detail(source)

    @router.get("/api/documents/{doc_name:path}")
    async def document_detail(req: Request, doc_name: str, scope: str = Query("visible")):
        entity_id = None
        stats_scope = "visible"
        if scope == "global":
            _, error = deps.require_system_admin_user(req)
            if error:
                return error
            stats_scope = "global"
        else:
            _, entity, error = deps.require_entity_member(req)
            if error:
                return error
            entity_id = entity.entity_id
        visible_sources = {
            row["source_path"]
            for row in vector_store.list_document_stats(entity_id=entity_id, scope=stats_scope)
        }
        if doc_name not in visible_sources:
            return JSONResponse({"error": "Document not found."}, status_code=404)
        return build_document_detail(doc_name)

    return router
