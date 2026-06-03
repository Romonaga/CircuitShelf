from __future__ import annotations

from typing import Any

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.api.dependencies import ApiDependencies


class InventoryImportPreviewRequest(BaseModel):
    text: str = ""


class InventoryImportApplyRequest(BaseModel):
    items: list[dict[str, Any]] = Field(default_factory=list)


def create_router(
    deps: ApiDependencies,
    *,
    lab_inventory_store: Any,
    project_finder_store: Any,
    parse_inventory_import: Any,
    inventory_photo_import_service: Any | None = None,
) -> APIRouter:
    router = APIRouter()

    @router.get("/api/inventory/parts")
    async def inventory_parts(req: Request):
        user, error = deps.require_authenticated_user(req)
        if error:
            return error
        return {"parts": lab_inventory_store.list_parts(deps.user_id_for_user(user))}

    @router.get("/api/inventory/locations")
    async def inventory_locations(req: Request):
        user, error = deps.require_authenticated_user(req)
        if error:
            return error
        return {"locations": lab_inventory_store.list_locations(deps.user_id_for_user(user))}

    @router.post("/api/inventory/locations")
    async def inventory_location_upsert(req: Request):
        user, error = deps.require_authenticated_user(req)
        if error:
            return error
        data = await req.json()
        try:
            location = lab_inventory_store.upsert_location(deps.user_id_for_user(user), data)
        except (TypeError, ValueError) as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        return {"location": location}

    @router.post("/api/inventory/parts")
    async def inventory_part_upsert(req: Request):
        user, error = deps.require_authenticated_user(req)
        if error:
            return error
        data = await req.json()
        try:
            part = lab_inventory_store.upsert_part(deps.user_id_for_user(user), data)
        except (TypeError, ValueError) as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        return {"part": part}

    @router.post("/api/inventory/import/preview")
    async def inventory_import_preview(req: Request, payload: InventoryImportPreviewRequest):
        user, error = deps.require_authenticated_user(req)
        if error:
            return error
        if not payload.text.strip():
            return JSONResponse({"error": "Inventory text is required."}, status_code=400)
        existing = lab_inventory_store.list_parts(deps.user_id_for_user(user))
        return parse_inventory_import(payload.text, existing)

    @router.post("/api/inventory/import/apply")
    async def inventory_import_apply(req: Request, payload: InventoryImportApplyRequest):
        user, error = deps.require_authenticated_user(req)
        if error:
            return error
        items = payload.items or []
        if not items:
            return JSONResponse({"error": "At least one inventory item is required."}, status_code=400)
        user_id = deps.user_id_for_user(user)
        existing_parts = {part["id"]: part for part in lab_inventory_store.list_parts(user_id)}
        saved = []
        for item in items[:200]:
            try:
                existing = existing_parts.get(str(item.get("existingPartId") or ""))
                if existing:
                    item = {
                        **item,
                        "id": existing["id"],
                        "displayName": existing["displayName"],
                        "partType": existing["partType"],
                        "quantity": max(0, int(existing.get("quantity") or 0)) + max(0, int(item.get("quantity") or 0)),
                        "locationId": existing.get("locationId") or item.get("locationId"),
                        "location": existing.get("location") or item.get("location") or "",
                        "notes": "\n".join(
                            note
                            for note in [
                                existing.get("notes") or "",
                                item.get("notes") or "",
                            ]
                            if note.strip()
                        ),
                        "aliases": sorted(set([*(existing.get("aliases") or []), *(item.get("aliases") or [])])),
                    }
                saved.append(lab_inventory_store.upsert_part(user_id, item))
            except (TypeError, ValueError) as exc:
                return JSONResponse({"error": str(exc)}, status_code=400)
        return {"parts": saved, "count": len(saved)}

    @router.post("/api/inventory/import/photo-preview")
    async def inventory_photo_import_preview(
        req: Request,
        file: UploadFile = File(...),
        note: str = Form(""),
    ):
        user, error = deps.require_authenticated_user(req)
        if error:
            return error
        if inventory_photo_import_service is None:
            return JSONResponse({"error": "Inventory photo import is not configured."}, status_code=503)
        content_type = file.content_type or ""
        if not content_type.startswith("image/"):
            return JSONResponse({"error": "Upload an image file for photo inventory import."}, status_code=400)
        image_bytes = await file.read()
        if not image_bytes:
            return JSONResponse({"error": "Image file is empty."}, status_code=400)
        if len(image_bytes) > 12 * 1024 * 1024:
            return JSONResponse({"error": "Image is too large. Use a photo under 12 MB."}, status_code=400)
        user_id = deps.user_id_for_user(user)
        entity = deps.entity_store.current_for_user(user_id)
        existing = lab_inventory_store.list_parts(user_id)
        try:
            return inventory_photo_import_service.preview(
                image_bytes=image_bytes,
                mime_type=content_type,
                note=note,
                entity_id=entity.get("id") if entity else None,
                user_id=user_id,
                existing_parts=existing,
            )
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)

    @router.delete("/api/inventory/parts/{part_id}")
    async def inventory_part_delete(part_id: str, req: Request):
        user, error = deps.require_authenticated_user(req)
        if error:
            return error
        removed = lab_inventory_store.delete_part(deps.user_id_for_user(user), part_id)
        if not removed:
            return JSONResponse({"error": "Inventory part not found."}, status_code=404)
        return {"ok": True}

    @router.get("/api/inventory/project-candidates")
    async def inventory_project_candidates(req: Request, limit: int = 24):
        user, error = deps.require_authenticated_user(req)
        if error:
            return error
        return project_finder_store.find(deps.user_id_for_user(user), limit=max(1, min(int(limit), 80)))

    return router
