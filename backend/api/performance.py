from __future__ import annotations

from fastapi import APIRouter, Query, Request

from backend.api.dependencies import ApiDependencies


def create_router(
    deps: ApiDependencies,
    *,
    performance_store,
) -> APIRouter:
    router = APIRouter()

    @router.get("/api/performance")
    async def performance_report(
        req: Request,
        hours: int = Query(24, ge=1, le=168),
        samples: int = Query(300, ge=10, le=2000),
        work: int = Query(80, ge=0, le=500),
    ):
        _, entity, error = deps.require_entity_member(req)
        if error:
            return error
        return performance_store.report(
            hours=hours,
            sample_limit=samples,
            work_limit=work,
            entity_id=entity.entity_id if entity else None,
        )

    return router
