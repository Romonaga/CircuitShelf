from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.api.dependencies import ApiDependencies


class LoginRequest(BaseModel):
    username: str = ""
    password: str = ""


class ProfileUpdateRequest(BaseModel):
    email: str = ""
    displayName: str = ""
    nickname: str = ""
    phone: str = ""
    address: str = ""


class PasswordUpdateRequest(BaseModel):
    currentPassword: str = ""
    newPassword: str = Field(default="", min_length=0)


class PreferenceUpdateRequest(BaseModel):
    value: dict = Field(default_factory=dict)


def create_router(deps: ApiDependencies, preference_keys: set[str]) -> APIRouter:
    router = APIRouter()

    @router.post("/api/login")
    async def login(payload: LoginRequest):
        user = deps.verify_user(payload.username, payload.password)
        if user:
            session = deps.user_store.create_session(user, ttl_seconds=deps.session_timeout_seconds())
            response = deps.user_payload(session)
            response.update({"ok": True, "token": session.token})
            return response
        return {"ok": False, "error": "Invalid credentials"}

    @router.post("/api/logout")
    async def logout(req: Request):
        deps.user_store.delete_session(deps.bearer_token_from_request(req))
        return {"ok": True}

    @router.get("/api/me")
    async def account_me(req: Request):
        user, error = deps.require_authenticated_user(req)
        if error:
            return error
        profile = deps.account_profile_store.get(deps.user_id_for_user(user))
        response = deps.user_payload(user)
        response["profile"] = profile
        return response

    @router.put("/api/account/profile")
    async def account_profile_update(req: Request, payload: ProfileUpdateRequest):
        user, error = deps.require_authenticated_user(req)
        if error:
            return error
        profile = deps.account_profile_store.update(deps.user_id_for_user(user), payload.model_dump())
        return {"profile": profile}

    @router.get("/api/user/preferences/{key}")
    async def user_preference_get(key: str, req: Request):
        user, error = deps.require_authenticated_user(req)
        if error:
            return error
        if key not in preference_keys:
            return JSONResponse({"error": "Unknown preference key."}, status_code=404)
        return {"key": key, "value": deps.user_preferences_store.get(deps.user_id_for_user(user), key, {})}

    @router.put("/api/user/preferences/{key}")
    async def user_preference_update(key: str, req: Request, payload: PreferenceUpdateRequest):
        user, error = deps.require_authenticated_user(req)
        if error:
            return error
        if key not in preference_keys:
            return JSONResponse({"error": "Unknown preference key."}, status_code=404)
        return {"key": key, "value": deps.user_preferences_store.set(deps.user_id_for_user(user), key, payload.value or {})}

    @router.put("/api/account/password")
    async def account_password_update(req: Request, payload: PasswordUpdateRequest):
        user, error = deps.require_authenticated_user(req)
        if error:
            return error
        if len(payload.newPassword) < 8:
            return JSONResponse({"error": "New password must be at least 8 characters."}, status_code=400)
        if not deps.user_store.change_password(deps.user_id_for_user(user), payload.currentPassword, payload.newPassword):
            return JSONResponse({"error": "Current password is not correct."}, status_code=400)
        return {"ok": True}

    return router
