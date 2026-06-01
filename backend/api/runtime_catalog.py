from __future__ import annotations

from fastapi import APIRouter, Request

from backend.api.dependencies import ApiDependencies


def create_router(deps: ApiDependencies, *, runtime_config_store) -> APIRouter:
    router = APIRouter()

    @router.get("/api/runtime/catalog")
    async def runtime_catalog(req: Request):
        _, error = deps.require_system_admin_user(req)
        if error:
            return error
        return runtime_config_store.admin_catalog()

    return router
