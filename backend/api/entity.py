from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel
from fastapi.responses import JSONResponse

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


class EntityMemberCreateRequest(BaseModel):
    username: str = ""
    temporaryPassword: str = ""
    email: str = ""
    displayName: str = ""
    nickname: str = ""
    phone: str = ""
    address: str = ""
    role: str = "user"
    forcePasswordChange: bool = True


class EntityMemberRoleRequest(BaseModel):
    role: str = "user"


class EntityMemberPasswordResetRequest(BaseModel):
    temporaryPassword: str = ""
    forcePasswordChange: bool = True


class EntityMemberDisableRequest(BaseModel):
    reason: str = ""


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

    @router.post("/api/entity/members")
    async def entity_member_create(req: Request, payload: EntityMemberCreateRequest):
        _, entity, error = deps.require_entity_admin(req)
        if error:
            return error
        try:
            created = deps.user_store.create_user(
                username=payload.username,
                password=payload.temporaryPassword,
                email=payload.email,
                display_name=payload.displayName,
                nickname=payload.nickname,
                phone=payload.phone,
                address=payload.address,
                is_admin=False,
                force_password_change=payload.forcePasswordChange,
            )
            deps.entity_store.upsert_membership(entity.entity_id, int(created["id"]), payload.role or "user")
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        return {"ok": True, "member": created, "members": deps.entity_store.members(entity.entity_id)}

    @router.put("/api/entity/members/{user_id}/role")
    async def entity_member_role_update(user_id: int, req: Request, payload: EntityMemberRoleRequest):
        _, entity, error = deps.require_entity_admin(req)
        if error:
            return error
        member = deps.entity_store.update_member_role(entity.entity_id, int(user_id), payload.role or "user")
        if not member:
            return JSONResponse({"error": "Entity member or role not found."}, status_code=404)
        return {"ok": True, "member": member, "members": deps.entity_store.members(entity.entity_id)}

    @router.post("/api/entity/members/{user_id}/reset-password")
    async def entity_member_password_reset(user_id: int, req: Request, payload: EntityMemberPasswordResetRequest):
        _, entity, error = deps.require_entity_admin(req)
        if error:
            return error
        if not any(member["userId"] == int(user_id) for member in deps.entity_store.members(entity.entity_id)):
            return JSONResponse({"error": "Entity member not found."}, status_code=404)
        try:
            member = deps.user_store.reset_password(
                int(user_id),
                payload.temporaryPassword,
                force_password_change=payload.forcePasswordChange,
            )
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        if not member:
            return JSONResponse({"error": "Entity member not found."}, status_code=404)
        return {"ok": True, "member": member, "members": deps.entity_store.members(entity.entity_id)}

    @router.post("/api/entity/members/{user_id}/unlock")
    async def entity_member_unlock(user_id: int, req: Request):
        _, entity, error = deps.require_entity_admin(req)
        if error:
            return error
        member = deps.entity_store.unlock_member(entity.entity_id, int(user_id))
        if not member:
            return JSONResponse({"error": "Entity member not found."}, status_code=404)
        return {"ok": True, "member": member}

    @router.post("/api/entity/members/{user_id}/disable")
    async def entity_member_disable(user_id: int, req: Request, payload: EntityMemberDisableRequest):
        user, entity, error = deps.require_entity_admin(req)
        if error:
            return error
        actor_id = deps.user_id_for_user(user)
        if actor_id == int(user_id):
            return JSONResponse({"error": "You cannot disable your own account."}, status_code=400)
        if entity.owner_user_id == int(user_id):
            return JSONResponse({"error": "The entity owner cannot be disabled from member management."}, status_code=400)
        member = deps.entity_store.disable_member(entity.entity_id, int(user_id), payload.reason)
        if not member:
            return JSONResponse({"error": "Entity member not found."}, status_code=404)
        return {"ok": True, "member": member, "members": deps.entity_store.members(entity.entity_id)}

    @router.post("/api/entity/members/{user_id}/enable")
    async def entity_member_enable(user_id: int, req: Request):
        _, entity, error = deps.require_entity_admin(req)
        if error:
            return error
        member = deps.entity_store.enable_member(entity.entity_id, int(user_id))
        if not member:
            return JSONResponse({"error": "Entity member not found."}, status_code=404)
        return {"ok": True, "member": member, "members": deps.entity_store.members(entity.entity_id)}

    @router.post("/api/entity/members/{user_id}/force-password-change")
    async def entity_member_force_password_change(user_id: int, req: Request):
        _, entity, error = deps.require_entity_admin(req)
        if error:
            return error
        member = deps.entity_store.force_member_password_change(entity.entity_id, int(user_id), True)
        if not member:
            return JSONResponse({"error": "Entity member not found."}, status_code=404)
        return {"ok": True, "member": member}

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
