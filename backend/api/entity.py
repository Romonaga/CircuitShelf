from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

from backend.api.dependencies import ApiDependencies


class PasswordPolicyRequest(BaseModel):
    minLength: int | None = None
    requireUpper: bool | None = None
    requireLower: bool | None = None
    requireNumber: bool | None = None
    requireSymbol: bool | None = None
    passwordChangeDays: int | None = None
    maxFailedAttempts: int | None = None
    lockoutMinutes: int | None = None


def create_router(deps: ApiDependencies) -> APIRouter:
    router = APIRouter()

    @router.get("/api/entity/current")
    async def entity_current(req: Request):
        user, entity, error = deps.require_entity_member(req)
        if error:
            return error
        return {"entity": entity.to_api(), "user": deps.user_payload(user)}

    @router.get("/api/entity/members")
    async def entity_members(req: Request):
        _, entity, error = deps.require_entity_admin(req)
        if error:
            return error
        return {"entity": entity.to_api(), "members": deps.entity_store.members(entity.entity_id)}

    @router.get("/api/entity/password-policy")
    async def entity_password_policy(req: Request):
        _, entity, error = deps.require_entity_admin(req)
        if error:
            return error
        return {"policy": deps.password_policy_store.effective_policy(entity.entity_id)}

    @router.put("/api/entity/password-policy")
    async def entity_password_policy_update(req: Request, payload: PasswordPolicyRequest):
        user, entity, error = deps.require_entity_admin(req)
        if error:
            return error
        return {
            "policy": deps.password_policy_store.upsert_policy(
                entity.entity_id,
                payload.model_dump(exclude_none=True),
                deps.user_id_for_user(user),
            )
        }

    @router.get("/api/system/password-policy")
    async def system_password_policy(req: Request):
        _, error = deps.require_system_admin_user(req)
        if error:
            return error
        return {"policy": deps.password_policy_store.effective_policy(None)}

    @router.put("/api/system/password-policy")
    async def system_password_policy_update(req: Request, payload: PasswordPolicyRequest):
        user, error = deps.require_system_admin_user(req)
        if error:
            return error
        return {
            "policy": deps.password_policy_store.upsert_policy(
                None,
                payload.model_dump(exclude_none=True),
                deps.user_id_for_user(user),
            )
        }

    return router
