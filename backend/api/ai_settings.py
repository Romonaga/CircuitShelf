from __future__ import annotations

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel

from backend.api.dependencies import ApiDependencies


class AIProviderSettingsRequest(BaseModel):
    enabled: bool = False
    apiKey: str | None = None
    clearApiKey: bool = False
    keyPolicy: str | None = None
    assistMode: str = "auto"
    defaultModel: str = ""
    monthlyBudget: float = 0
    warnPercent: int = 80
    stopPercent: int = 100
    pricingOverrides: list[dict] | None = None


def create_router(deps: ApiDependencies) -> APIRouter:
    router = APIRouter()

    @router.get("/api/ai/pricing")
    async def pricing_catalog(req: Request, provider: str = "openai"):
        user, error = deps.require_authenticated_user(req)
        if error:
            return error
        return {"pricing": deps.ai_provider_store.pricing_catalog(provider)}

    @router.get("/api/account/ai-provider")
    async def account_ai_provider(req: Request, provider: str = "openai"):
        user, error = deps.require_authenticated_user(req)
        if error:
            return error
        return {
            "settings": deps.ai_provider_store.get_user_settings(deps.user_id_for_user(user), provider),
            "pricing": deps.ai_provider_store.pricing_catalog(provider),
        }

    @router.put("/api/account/ai-provider")
    async def account_ai_provider_update(req: Request, payload: AIProviderSettingsRequest, provider: str = "openai"):
        user, error = deps.require_authenticated_user(req)
        if error:
            return error
        settings = deps.ai_provider_store.save_user_settings(
            deps.user_id_for_user(user),
            payload.model_dump(),
            provider,
        )
        return {"settings": settings}

    @router.get("/api/entity/ai-provider")
    async def entity_ai_provider(req: Request, provider: str = "openai"):
        _, entity, error = deps.require_entity_admin(req)
        if error:
            return error
        return {
            "settings": deps.ai_provider_store.get_entity_settings(entity.entity_id, provider),
            "pricing": deps.ai_provider_store.pricing_catalog(provider),
        }

    @router.put("/api/entity/ai-provider")
    async def entity_ai_provider_update(req: Request, payload: AIProviderSettingsRequest, provider: str = "openai"):
        user, entity, error = deps.require_entity_admin(req)
        if error:
            return error
        settings = deps.ai_provider_store.save_entity_settings(
            entity.entity_id,
            payload.model_dump(),
            deps.user_id_for_user(user),
            provider,
        )
        return {"settings": settings}

    @router.get("/api/system/ai-provider")
    async def system_ai_provider(req: Request, provider: str = "openai"):
        _, error = deps.require_system_admin_user(req)
        if error:
            return error
        return {
            "settings": deps.ai_provider_store.get_system_settings(provider),
            "pricing": deps.ai_provider_store.pricing_catalog(provider),
        }

    @router.put("/api/system/ai-provider")
    async def system_ai_provider_update(req: Request, payload: AIProviderSettingsRequest, provider: str = "openai"):
        user, error = deps.require_system_admin_user(req)
        if error:
            return error
        settings = deps.ai_provider_store.save_system_settings(
            payload.model_dump(),
            deps.user_id_for_user(user),
            provider,
        )
        return {"settings": settings}

    @router.get("/api/entity/ai-usage")
    async def entity_ai_usage(
        req: Request,
        days: int = Query(31, ge=1, le=366),
        limit: int = Query(250, ge=1, le=1000),
    ):
        _, entity, error = deps.require_entity_admin(req)
        if error:
            return error
        return deps.ai_provider_store.usage_report(entity_id=entity.entity_id, days=days, limit=limit)

    @router.get("/api/system/ai-usage")
    async def system_ai_usage(
        req: Request,
        days: int = Query(31, ge=1, le=366),
        limit: int = Query(250, ge=1, le=1000),
    ):
        _, error = deps.require_system_admin_user(req)
        if error:
            return error
        return deps.ai_provider_store.usage_report(entity_id=None, days=days, limit=limit)

    return router
