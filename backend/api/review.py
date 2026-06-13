from __future__ import annotations

import os
import json
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from backend.domain.statuses import DocumentStatusId


class DocumentActionRequest(BaseModel):
    source: str = ""
    includeImages: bool = True
    deleteFile: bool = True
    minQuality: float | None = None


class DocumentScopeRequest(BaseModel):
    source: str = ""
    scope: str = "global"
    reason: str = ""


class DocumentBatchActionRequest(BaseModel):
    sources: list[str] = []
    action: str = "approve"
    includeImages: bool = True
    deleteFile: bool = True
    scope: str = "global"
    minQuality: float | None = None


def review_document_payload(row: Any) -> dict:
    return {
        "source": row["source_path"],
        "displayName": row["display_name"],
        "status": row["status"],
        "statusId": row.get("status_id"),
        "entityId": row.get("entity_id"),
        "isGlobal": bool(row.get("is_global")),
        "entityName": row.get("entity_name") or "",
        "scopeLabel": "Global corpus" if row.get("is_global") else f"Entity: {row.get('entity_name') or 'Private'}",
        "sizeBytes": int(row["size_bytes"] or 0),
        "fileExtension": row["file_extension"],
        "chunkCount": int(row["chunk_count"] or 0),
        "imageCount": int(row["image_count"] or 0),
        "rawChunkCount": int(row["raw_chunk_count"] or 0),
        "droppedChunkCount": int(row["dropped_chunk_count"] or 0),
        "extractedImageCount": int(row["extracted_image_count"] or 0),
        "storedImageCount": int(row["stored_image_count"] or 0),
        "indexedImageTextCount": int(row["indexed_image_text_count"] or 0),
        "ocrImageTextCount": int(row["ocr_image_text_count"] or 0),
        "avgQuality": float(row["avg_quality"] or 0.0),
        "lowQualityCount": int(row["low_quality_count"] or 0),
        "lastIngestedAt": row["last_ingested_at"].isoformat() if row["last_ingested_at"] else None,
        "lastError": row["last_error"],
        "updatedAt": row["updated_at"].isoformat() if row["updated_at"] else None,
    }


def review_chunk_payload(row: Any) -> dict:
    return {
        "index": int(row["chunk_index"]),
        "section": row["section_title"] or "Unknown",
        "category": row["category"] or "Uncategorized",
        "page": row["page_number"],
        "tokens": int(row["token_count"] or 0),
        "quality": float(row["quality_score"] or 0.0),
        "isOcr": bool(row["is_ocr"]),
        "hasMath": bool(row["has_math"]),
        "sourceImageId": row["source_image_key"],
        "qualityFlags": list(row["quality_flags"] or []),
        "preview": row["chunk_text"][:700],
    }


def review_image_payload(row: Any) -> dict:
    return {
        "imageKey": row["image_key"],
        "caption": row["caption"] or row["image_key"],
        "page": row["page_number"],
        "width": int(row["width_px"] or 0),
        "height": int(row["height_px"] or 0),
        "imageMimeType": row["image_mime_type"] or "image/png",
        "imageBase64": row["image_base64"],
        "ocrText": row.get("ocr_text") or "",
    }


def code_sample_payload(row: Any | None) -> dict | None:
    if not row:
        return None
    return {
        "packKey": row.get("pack_key") or "",
        "packDisplayName": row.get("pack_display_name") or row.get("pack_key") or "",
        "rootPath": row.get("root_path") or "",
        "summary": row.get("pack_summary") or "",
        "packBoard": row.get("pack_board") or "",
        "packFramework": row.get("pack_framework") or "",
        "packLanguages": list(row.get("pack_languages") or []),
        "packLibraries": list(row.get("pack_libraries") or []),
        "packComponents": list(row.get("pack_components") or []),
        "packInterfaces": list(row.get("pack_interfaces") or []),
        "relativePath": row.get("relative_path") or "",
        "language": row.get("language") or "",
        "role": row.get("role") or "",
        "board": row.get("board") or row.get("pack_board") or "",
        "framework": row.get("framework") or row.get("pack_framework") or "",
        "libraries": list(row.get("libraries") or row.get("pack_libraries") or []),
        "components": list(row.get("components") or row.get("pack_components") or []),
        "interfaces": list(row.get("interfaces") or row.get("pack_interfaces") or []),
        "pins": list(row.get("pins") or []),
        "updatedAt": row["updated_at"].isoformat() if row.get("updated_at") else None,
    }


def review_intelligence_payload(rows: list[dict], source: str, get_or_build_datasheet_intelligence: Callable[..., dict]) -> dict | None:
    chunks = []
    metadata = []
    for row in rows:
        chunks.append(row.get("chunk_text") or "")
        metadata.append({
            "source": source,
            "parent_source": source,
            "page": row.get("page_number"),
            "section": row.get("section_title") or "Unknown",
            "category": row.get("category") or "Uncategorized",
            "source_image_id": row.get("source_image_key"),
        })
    if not chunks:
        return None
    intelligence = get_or_build_datasheet_intelligence(source, chunks, metadata)
    if not intelligence or not intelligence.get("componentName"):
        return None
    return intelligence


def scope_audit_payload(row: Any) -> dict:
    return {
        "id": int(row["id"]),
        "source": row["source_path"],
        "previousIsGlobal": row.get("previous_is_global"),
        "previousEntityId": row.get("previous_entity_id"),
        "previousEntityName": row.get("previous_entity_name") or "",
        "newIsGlobal": bool(row.get("new_is_global")),
        "newEntityId": row.get("new_entity_id"),
        "newEntityName": row.get("new_entity_name") or "",
        "changedByUserId": row.get("changed_by_user_id"),
        "changedByUsername": row.get("changed_by_username") or "",
        "reason": row.get("reason") or "",
        "createdAt": row["created_at"].isoformat() if row.get("created_at") else None,
    }


def create_router(
    *,
    deps: Any,
    vector_store: Any,
    image_store: Any,
    training_dir: str,
    refresh_active_state_from_db: Callable[[], int],
    start_index_check: Callable[..., dict],
    remove_document_from_store: Callable[..., tuple[dict, int]],
    get_or_build_datasheet_intelligence: Callable[..., dict],
) -> APIRouter:
    router = APIRouter()

    def source_file_response(source: str):
        rel_source = vector_store.rel_path_for_source(source, {"source": source})
        training_root = os.path.abspath(training_dir)
        target = os.path.abspath(os.path.join(training_dir, rel_source))
        if not target.startswith(training_root + os.sep):
            return JSONResponse({"error": "Document path is not allowed."}, status_code=400)
        if not os.path.exists(target) or not os.path.isfile(target):
            return JSONResponse({"error": "Source file is not available on disk."}, status_code=404)
        return FileResponse(target, filename=os.path.basename(rel_source), media_type="application/octet-stream")

    def authorize_review_read(req: Request, source: str):
        scope = vector_store.get_document_scope(source)
        if not scope:
            return None, None, JSONResponse({"error": "Document not found."}, status_code=404)
        if scope.get("is_global"):
            user, error = deps.require_system_admin_user(req)
            return user, scope, error
        user, entity, error = deps.require_entity_admin(req)
        if error:
            return user, scope, error
        if int(scope.get("entity_id") or 0) != int(entity.entity_id):
            return user, scope, JSONResponse({"error": "Document is not in your entity."}, status_code=403)
        return user, scope, None

    def response_error_message(response: JSONResponse) -> str:
        try:
            payload = json.loads(response.body.decode("utf-8"))
        except Exception:
            return "Request failed."
        return str(payload.get("error") or payload.get("message") or "Request failed.")

    def normalized_review_min_quality(value: float | None) -> float | None:
        if value is None:
            return None
        try:
            threshold = float(value)
        except (TypeError, ValueError):
            return None
        return max(0.0, min(1.0, threshold))

    def unique_sources(sources: list[str]) -> list[str]:
        seen = set()
        clean = []
        for source in sources:
            value = str(source or "").strip()
            if not value or value in seen:
                continue
            seen.add(value)
            clean.append(value)
        return clean[:1000]

    def batch_result(source: str, *, ok: bool, action: str, error: str = "", status_code: int = 200, extra: dict | None = None) -> dict:
        payload = {
            "source": source,
            "ok": ok,
            "action": action,
            "statusCode": status_code,
        }
        if error:
            payload["error"] = error
        if extra:
            payload.update(extra)
        return payload

    def active_entity_for_scope_change(user: Any, target_scope: str):
        if target_scope == "global":
            return None, True, None
        if target_scope != "entity":
            return None, None, JSONResponse({"error": "Scope must be global or entity."}, status_code=400)
        active_entity = deps.entity_store.current_for_user(deps.user_id_for_user(user))
        if not active_entity:
            return None, None, JSONResponse({"error": "No active entity available for private scope."}, status_code=400)
        return active_entity.entity_id, False, None

    @router.get("/api/review/documents")
    async def review_documents(req: Request):
        user, error = deps.require_authenticated_user(req)
        if error:
            return error
        if getattr(user, "can_manage_system", False):
            rows = vector_store.list_review_documents(scope="all")
        else:
            _, entity, entity_error = deps.require_entity_admin(req)
            if entity_error:
                return entity_error
            rows = vector_store.list_review_documents(scope="entity", entity_id=entity.entity_id)
        return {"documents": [review_document_payload(row) for row in rows]}

    @router.get("/api/review/document")
    async def review_document(req: Request, source: str, limit: int = 50):
        _, _, error = authorize_review_read(req, source)
        if error:
            return error
        rows = vector_store.review_document_chunks(source, limit=max(1, min(int(limit), 500)))
        intelligence_rows = vector_store.review_document_all_chunks(source)
        audit = vector_store.document_scope_audit(source, limit=25)
        intelligence = review_intelligence_payload(intelligence_rows, source, get_or_build_datasheet_intelligence)
        code_sample = code_sample_payload(vector_store.code_sample_for_source(source))
        if not rows:
            return {
                "document": source,
                "chunks": [],
                "scopeAudit": [scope_audit_payload(row) for row in audit],
                "intelligence": intelligence,
                "codeSample": code_sample,
            }
        return {
            "document": source,
            "displayName": rows[0]["display_name"],
            "status": rows[0]["status"],
            "chunks": [review_chunk_payload(row) for row in rows],
            "scopeAudit": [scope_audit_payload(row) for row in audit],
            "intelligence": intelligence,
            "codeSample": code_sample,
        }

    @router.get("/api/review/document/images")
    async def review_document_images(req: Request, source: str):
        _, _, error = authorize_review_read(req, source)
        if error:
            return error
        rows = image_store.list_review_images(source)
        return {"document": source, "images": [review_image_payload(row) for row in rows]}

    @router.get("/api/review/document/download")
    async def review_document_download(req: Request, source: str):
        _, _, error = authorize_review_read(req, source)
        if error:
            return error
        return source_file_response(source)

    @router.post("/api/review/document/approve")
    async def review_document_approve(req: Request, payload: DocumentActionRequest):
        user, _, error = authorize_review_read(req, payload.source)
        if error:
            return error
        source = payload.source
        if not payload.includeImages:
            image_store.delete_document_images(source)
        prune_result = vector_store.prune_document_chunks_below_quality(
            source,
            normalized_review_min_quality(payload.minQuality),
        )
        row = vector_store.set_document_status(source, DocumentStatusId.INDEXED, user.username)
        if not row:
            return JSONResponse({"error": "Document not found."}, status_code=404)
        image_count = refresh_active_state_from_db()
        return {"ok": True, "document": dict(row), "imageCount": image_count, **prune_result}

    @router.post("/api/review/documents/batch")
    async def review_documents_batch(req: Request, payload: DocumentBatchActionRequest):
        action = payload.action.strip().lower()
        sources = unique_sources(payload.sources)
        if not sources:
            return JSONResponse({"error": "Select at least one document."}, status_code=400)
        if action not in {"approve", "remove", "reindex", "scope"}:
            return JSONResponse({"error": "Batch action must be approve, remove, reindex, or scope."}, status_code=400)

        results = []
        changed_catalog = False
        scope_user = None
        scope_entity_id = None
        scope_is_global = None
        if action == "scope":
            scope_user, scope_error = deps.require_system_admin_user(req)
            if scope_error:
                return scope_error
            scope_entity_id, scope_is_global, scope_target_error = active_entity_for_scope_change(
                scope_user,
                payload.scope.strip().lower(),
            )
            if scope_target_error:
                return scope_target_error

        for source in sources:
            try:
                if action == "approve":
                    user, _, error = authorize_review_read(req, source)
                    if error:
                        results.append(batch_result(source, ok=False, action=action, error=response_error_message(error), status_code=error.status_code))
                        continue
                    if not payload.includeImages:
                        image_store.delete_document_images(source)
                    prune_result = vector_store.prune_document_chunks_below_quality(
                        source,
                        normalized_review_min_quality(payload.minQuality),
                    )
                    row = vector_store.set_document_status(source, DocumentStatusId.INDEXED, user.username)
                    if not row:
                        results.append(batch_result(source, ok=False, action=action, error="Document not found.", status_code=404))
                        continue
                    changed_catalog = True
                    results.append(batch_result(source, ok=True, action=action, extra={"document": dict(row), **prune_result}))
                    continue

                if action == "remove":
                    _, _, error = authorize_review_read(req, source)
                    if error:
                        results.append(batch_result(source, ok=False, action=action, error=response_error_message(error), status_code=error.status_code))
                        continue
                    result, status_code = remove_document_from_store(source, delete_file=payload.deleteFile)
                    if status_code != 200:
                        results.append(batch_result(source, ok=False, action=action, error=str(result.get("error") or "Remove failed."), status_code=status_code))
                        continue
                    changed_catalog = True
                    results.append(batch_result(source, ok=True, action=action, extra={"document": result.get("document")}))
                    continue

                if action == "reindex":
                    user, _, error = authorize_review_read(req, source)
                    if error:
                        results.append(batch_result(source, ok=False, action=action, error=response_error_message(error), status_code=error.status_code))
                        continue
                    result = start_index_check(
                        f"reindex:{source}",
                        requested_by_user_id=deps.user_id_for_user(user),
                    )
                    results.append(batch_result(source, ok=True, action=action, extra={"queued": True, "indexing": result}))
                    continue

                if action == "scope":
                    row = vector_store.set_document_scope(
                        source,
                        is_global=bool(scope_is_global),
                        entity_id=scope_entity_id,
                        changed_by_user_id=deps.user_id_for_user(scope_user),
                        reason=f"Batch review changed scope to {payload.scope.strip().lower()}",
                    )
                    if not row:
                        results.append(batch_result(source, ok=False, action=action, error="Document not found.", status_code=404))
                        continue
                    changed_catalog = True
                    results.append(batch_result(source, ok=True, action=action, extra={"document": dict(row)}))
            except Exception as exc:
                results.append(batch_result(source, ok=False, action=action, error=str(exc), status_code=500))

        if changed_catalog:
            image_count = refresh_active_state_from_db()
        else:
            image_count = None
        ok_count = sum(1 for item in results if item.get("ok"))
        return {
            "ok": ok_count == len(results),
            "action": action,
            "count": len(results),
            "okCount": ok_count,
            "failedCount": len(results) - ok_count,
            "results": results,
            "imageCount": image_count,
        }

    @router.post("/api/review/document/reindex")
    async def review_document_reindex(req: Request, payload: DocumentActionRequest):
        user, _, error = authorize_review_read(req, payload.source)
        if error:
            return error
        result = start_index_check(
            f"reindex:{payload.source}",
            requested_by_user_id=deps.user_id_for_user(user),
        )
        return {"ok": True, "queued": True, "source": payload.source, "indexing": result}

    @router.post("/api/review/document/remove")
    async def review_document_remove(req: Request, payload: DocumentActionRequest):
        _, _, error = authorize_review_read(req, payload.source)
        if error:
            return error
        result, status_code = remove_document_from_store(payload.source, delete_file=payload.deleteFile)
        if status_code != 200:
            return JSONResponse(result, status_code=status_code)
        return result

    @router.post("/api/document/remove")
    async def indexed_document_remove(req: Request, payload: DocumentActionRequest):
        _, _, error = authorize_review_read(req, payload.source)
        if error:
            return error
        result, status_code = remove_document_from_store(payload.source, delete_file=payload.deleteFile)
        if status_code != 200:
            return JSONResponse(result, status_code=status_code)
        return result

    @router.post("/api/review/document/scope")
    async def review_document_scope(req: Request, payload: DocumentScopeRequest):
        user, error = deps.require_system_admin_user(req)
        if error:
            return error
        target_scope = payload.scope.strip().lower()
        entity_id, is_global, target_error = active_entity_for_scope_change(user, target_scope)
        if target_error:
            return target_error
        try:
            row = vector_store.set_document_scope(
                payload.source,
                is_global=is_global,
                entity_id=entity_id,
                changed_by_user_id=deps.user_id_for_user(user),
                reason=payload.reason or f"Changed to {target_scope}",
            )
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        if not row:
            return JSONResponse({"error": "Document not found."}, status_code=404)
        refresh_active_state_from_db()
        return {"ok": True, "document": dict(row), "scopeAudit": [scope_audit_payload(item) for item in vector_store.document_scope_audit(payload.source)]}

    return router
