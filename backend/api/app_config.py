from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse


def create_router(
    *,
    config: Any,
    models: list[str],
    default_model: str,
    auth_configured: Callable[[], bool],
    session_timeout_seconds: Callable[[], int],
    build_readiness_status: Callable[[], tuple[bool, dict]],
) -> APIRouter:
    router = APIRouter()

    @router.get("/healthz")
    async def healthz():
        return {"status": "ok", "service": "CircuitShelf"}

    @router.get("/readyz")
    async def readyz():
        ready, payload = build_readiness_status()
        return JSONResponse(payload, status_code=200 if ready else 503)

    @router.get("/api/app-config")
    async def app_config():
        return {
            "siteName": config.get("SITE_NAME", "CircuitShelf"),
            "models": models,
            "defaultModel": default_model,
            "authConfigured": auth_configured(),
            "retrievalStrategies": ["Vector only", "Vector + CrossEncoder"],
            "statusPollIntervalSeconds": max(5, int(config.get("STATUS_POLL_INTERVAL_SECONDS", 15))),
            "activeStatusPollIntervalSeconds": max(1, int(config.get("STATUS_POLL_ACTIVE_INTERVAL_SECONDS", 3))),
            "sessionTimeoutSeconds": session_timeout_seconds(),
            "defaults": {
                "topK": 15,
                "distanceThreshold": 4.0,
                "maxTokens": 1800,
                "showFullText": False,
                "bypassCache": True,
                "strategy": "Vector + CrossEncoder",
            },
        }

    return router
