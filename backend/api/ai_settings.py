from __future__ import annotations

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from backend.api.dependencies import ApiDependencies
from backend.services.ai_usage_export import ai_usage_report_to_csv


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
            "pricingVariants": deps.ai_provider_store.pricing_variants(provider),
        }

    @router.get("/api/account/ai-provider/models")
    async def account_ai_provider_models(req: Request, provider: str = "openai"):
        user, error = deps.require_authenticated_user(req)
        if error:
            return error
        try:
            models = deps.openai_model_service.list_models_for_scope(
                scope="user",
                provider=provider,
                user_id=deps.user_id_for_user(user),
            )
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        return {"models": models}

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
            "pricingVariants": deps.ai_provider_store.pricing_variants(provider),
        }

    @router.get("/api/entity/ai-provider/models")
    async def entity_ai_provider_models(req: Request, provider: str = "openai"):
        _, entity, error = deps.require_entity_admin(req)
        if error:
            return error
        try:
            models = deps.openai_model_service.list_models_for_scope(
                scope="entity",
                provider=provider,
                entity_id=entity.entity_id,
            )
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        return {"models": models}

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
            "pricingVariants": deps.ai_provider_store.pricing_variants(provider),
        }

    @router.get("/api/system/ai-provider/models")
    async def system_ai_provider_models(req: Request, provider: str = "openai"):
        _, error = deps.require_system_admin_user(req)
        if error:
            return error
        try:
            models = deps.openai_model_service.list_models_for_scope(scope="system", provider=provider)
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        return {"models": models}

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

    @router.get("/api/entity/ai-usage/export")
    async def entity_ai_usage_export(
        req: Request,
        days: int = Query(31, ge=1, le=366),
    ):
        _, entity, error = deps.require_entity_admin(req)
        if error:
            return error
        report = deps.ai_provider_store.usage_report(entity_id=entity.entity_id, days=days, limit=10000)
        return Response(
            ai_usage_report_to_csv(report),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=circuit-shelf-entity-ai-usage.csv"},
        )

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

    @router.get("/api/system/ai-usage/export")
    async def system_ai_usage_export(
        req: Request,
        days: int = Query(31, ge=1, le=366),
    ):
        _, error = deps.require_system_admin_user(req)
        if error:
            return error
        report = deps.ai_provider_store.usage_report(entity_id=None, days=days, limit=10000)
        return Response(
            ai_usage_report_to_csv(report),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=circuit-shelf-system-ai-usage.csv"},
        )

    return router
