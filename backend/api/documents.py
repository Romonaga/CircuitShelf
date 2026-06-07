from __future__ import annotations

import os
from typing import Any

from collections.abc import Callable

from fastapi import APIRouter, File, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from backend.api.dependencies import ApiDependencies
from backend.services.document_detail_builder import DocumentDetailBuilder
from backend.services.document_upload_writer import write_uploaded_documents
from backend.services.upload_session_guard import complete_upload_session, mark_upload_session_active


def create_router(
    deps: ApiDependencies,
    *,
    training_dir: str,
    supported_training_extensions: Callable[[], set[str]],
    vector_store: Any,
    image_store: Any,
    state: Any,
    trace_logger: Any,
    start_index_check: Callable[..., dict],
    extract_page_number: Callable[[str], int | None],
    document_source_from_metadata: Callable[[str, dict], str],
    source_image_id_from_metadata: Callable[[str, dict], str | None],
    extract_pinout_map: Callable[[list, list, str], dict],
    get_or_build_datasheet_intelligence: Callable[..., dict],
    display_source_name: Callable[[str], str],
) -> APIRouter:
    router = APIRouter()
    detail_builder = DocumentDetailBuilder(
        state=state,
        vector_store=vector_store,
        image_store=image_store,
        extract_page_number=extract_page_number,
        document_source_from_metadata=document_source_from_metadata,
        source_image_id_from_metadata=source_image_id_from_metadata,
        extract_pinout_map=extract_pinout_map,
        get_or_build_datasheet_intelligence=get_or_build_datasheet_intelligence,
        display_source_name=display_source_name,
    )

    def visible_document_sources(req: Request, scope: str):
        entity_id = None
        stats_scope = "visible"
        if scope == "global":
            _, error = deps.require_system_admin_user(req)
            if error:
                return None, error
            stats_scope = "global"
        else:
            _, entity, error = deps.require_entity_member(req)
            if error:
                return None, error
            entity_id = entity.entity_id
        return {
            row["source_path"]
            for row in vector_store.list_document_stats(entity_id=entity_id, scope=stats_scope)
        }, None

    def source_file_response(source: str):
        rel_source = vector_store.rel_path_for_source(source, {"source": source})
        training_root = os.path.abspath(training_dir)
        target = os.path.abspath(os.path.join(training_dir, rel_source))
        if not target.startswith(training_root + os.sep):
            return JSONResponse({"error": "Document path is not allowed."}, status_code=400)
        if not os.path.exists(target) or not os.path.isfile(target):
            return JSONResponse({"error": "Source file is not available on disk."}, status_code=404)
        return FileResponse(target, filename=os.path.basename(rel_source), media_type="application/octet-stream")

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
        defer_index: bool = Query(False),
        upload_session: str | None = Query(None),
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

        mark_upload_session_active(training_dir, upload_session)
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
        index_job = (
            start_index_check(f"upload:{filename}", requested_by_user_id=created_by_user_id)
            if uploaded_files and not defer_index
            else {"started": False, "deferred": bool(uploaded_files)}
        )
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
        defer_index: bool = Query(False),
        upload_session: str | None = Query(None),
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

        mark_upload_session_active(training_dir, upload_session)
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
        index_job = (
            start_index_check(reason, requested_by_user_id=created_by_user_id)
            if uploaded_files and not defer_index
            else {"started": False, "deferred": bool(uploaded_files)}
        )
        return {
            "ok": True,
            "files": uploaded_files,
            "skippedFiles": skipped_files,
            "count": len(uploaded_files),
            "skippedCount": len(skipped_files),
            "bytes": sum(item["bytes"] for item in uploaded_files),
            "indexing": index_job,
        }

    @router.post("/api/documents/upload-complete")
    async def upload_complete(
        req: Request,
        scope: str = Query("entity"),
        upload_session: str = Query(...),
        uploaded_count: int = Query(0),
        start_index: bool = Query(True),
    ):
        created_by_user_id = None
        if scope == "global":
            user, error = deps.require_system_admin_user(req)
            if error:
                return error
            created_by_user_id = deps.user_id_for_user(user)
        else:
            user, _, error = deps.require_entity_admin(req)
            if error:
                return error
            created_by_user_id = deps.user_id_for_user(user)

        complete_upload_session(training_dir, upload_session)
        index_job = (
            start_index_check(f"upload-batch:{max(0, uploaded_count)}", requested_by_user_id=created_by_user_id)
            if start_index and uploaded_count > 0
            else {"started": False}
        )
        return {"ok": True, "indexing": index_job}

    @router.get("/api/document")
    async def document_detail_query(req: Request, source: str, scope: str = Query("visible")):
        visible_sources, error = visible_document_sources(req, scope)
        if error:
            return error
        if source not in visible_sources:
            return JSONResponse({"error": "Document not found."}, status_code=404)
        return detail_builder.build(source)

    @router.get("/api/document/download")
    async def document_download(req: Request, source: str, scope: str = Query("visible")):
        visible_sources, error = visible_document_sources(req, scope)
        if error:
            return error
        if source not in visible_sources:
            return JSONResponse({"error": "Document not found."}, status_code=404)
        return source_file_response(source)

    @router.get("/api/documents/{doc_name:path}")
    async def document_detail(req: Request, doc_name: str, scope: str = Query("visible")):
        visible_sources, error = visible_document_sources(req, scope)
        if error:
            return error
        if doc_name not in visible_sources:
            return JSONResponse({"error": "Document not found."}, status_code=404)
        return detail_builder.build(doc_name)

    return router
