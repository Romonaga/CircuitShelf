from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class SettingUpdateRequest(BaseModel):
    value: Any = None


def create_router(
    *,
    require_admin_user: Callable[[Request], tuple[Any, Any]],
    settings_store: Any,
    runtime_settings: Any,
    trace_logger: Any,
    start_index_check: Callable[[str], dict],
) -> APIRouter:
    router = APIRouter()

    @router.get("/api/settings")
    async def settings_list(req: Request):
        _, error = require_admin_user(req)
        if error:
            return error
        return {"settings": settings_store.list_editable()}

    @router.put("/api/settings/{key}")
    async def settings_update(key: str, req: Request, payload: SettingUpdateRequest):
        _, error = require_admin_user(req)
        if error:
            return error
        try:
            updated = settings_store.update_setting(key, payload.value)
            change = runtime_settings.apply_update(key, updated["value"])
            if change.runtime_applied:
                trace_logger.info(f"⚙️ Applied runtime setting update for {key}.")
            elif change.restart_required:
                trace_logger.info(f"⚙️ Stored setting update for {key}; restart required to apply it.")
            return {"setting": updated}
        except KeyError as exc:
            return JSONResponse({"error": str(exc)}, status_code=404)
        except (PermissionError, ValueError, TypeError) as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)

    @router.post("/api/index/check")
    async def index_check(req: Request):
        _, error = require_admin_user(req)
        if error:
            return error
        result = start_index_check("manual")
        return {"ok": True, **result}

    return router
