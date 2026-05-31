from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
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
) -> APIRouter:
    router = APIRouter()

    @router.get("/api/inventory/parts")
    async def inventory_parts(req: Request):
        user, error = deps.require_authenticated_user(req)
        if error:
            return error
        return {"parts": lab_inventory_store.list_parts(deps.user_id_for_user(user))}

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
                        "displayName": existing["displayName"],
                        "partType": existing["partType"],
                        "quantity": max(int(existing.get("quantity") or 0), int(item.get("quantity") or 0)),
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
