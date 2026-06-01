from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class DocumentActionRequest(BaseModel):
    source: str = ""
    includeImages: bool = True
    deleteFile: bool = True


class DocumentScopeRequest(BaseModel):
    source: str = ""
    scope: str = "global"
    reason: str = ""


def review_document_payload(row: Any) -> dict:
    return {
        "source": row["source_path"],
        "displayName": row["display_name"],
        "status": row["status"],
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
    }


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
    refresh_active_state_from_db: Callable[[], int],
    reindex_review_source: Callable[[str], Any],
    remove_document_from_store: Callable[..., tuple[dict, int]],
) -> APIRouter:
    router = APIRouter()

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
        audit = vector_store.document_scope_audit(source, limit=25)
        if not rows:
            return {"document": source, "chunks": [], "scopeAudit": [scope_audit_payload(row) for row in audit]}
        return {
            "document": source,
            "displayName": rows[0]["display_name"],
            "status": rows[0]["status"],
            "chunks": [review_chunk_payload(row) for row in rows],
            "scopeAudit": [scope_audit_payload(row) for row in audit],
        }

    @router.get("/api/review/document/images")
    async def review_document_images(req: Request, source: str):
        _, _, error = authorize_review_read(req, source)
        if error:
            return error
        rows = image_store.list_review_images(source)
        return {"document": source, "images": [review_image_payload(row) for row in rows]}

    @router.post("/api/review/document/approve")
    async def review_document_approve(req: Request, payload: DocumentActionRequest):
        user, _, error = authorize_review_read(req, payload.source)
        if error:
            return error
        source = payload.source
        if not payload.includeImages:
            image_store.delete_document_images(source)
        row = vector_store.set_document_status(source, "indexed", user.username)
        if not row:
            return JSONResponse({"error": "Document not found."}, status_code=404)
        image_count = refresh_active_state_from_db()
        return {"ok": True, "document": dict(row), "imageCount": image_count}

    @router.post("/api/review/document/reindex")
    async def review_document_reindex(req: Request, payload: DocumentActionRequest):
        _, _, error = authorize_review_read(req, payload.source)
        if error:
            return error
        try:
            result = reindex_review_source(payload.source)
        except FileNotFoundError as exc:
            return JSONResponse({"error": str(exc)}, status_code=404)
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        return {"ok": True, "chunks": result.chunks, "droppedChunks": result.dropped_chunks, "images": result.images}

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
        active_entity = deps.entity_store.current_for_user(deps.user_id_for_user(user))
        if target_scope == "global":
            entity_id = None
            is_global = True
        elif target_scope == "entity":
            if not active_entity:
                return JSONResponse({"error": "No active entity available for private scope."}, status_code=400)
            entity_id = active_entity.entity_id
            is_global = False
        else:
            return JSONResponse({"error": "Scope must be global or entity."}, status_code=400)
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
