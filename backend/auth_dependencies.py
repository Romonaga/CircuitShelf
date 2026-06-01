from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


class AuthDependencyService:
    def __init__(
        self,
        *,
        database: Any,
        user_store: Any,
        entity_store: Any,
        session_timeout_seconds: Any,
    ):
        self.database = database
        self.user_store = user_store
        self.entity_store = entity_store
        self.session_timeout_seconds = session_timeout_seconds

    def verify_user(self, username: str, password: str):
        return self.user_store.verify_user(username, password)

    @staticmethod
    def bearer_token_from_request(req: Request) -> str:
        header = req.headers.get("authorization", "")
        prefix = "Bearer "
        if header.startswith(prefix):
            return header[len(prefix):].strip()
        return ""

    @staticmethod
    def username_for_user(user) -> str | None:
        return getattr(user, "username", None) if user else None

    @staticmethod
    def user_id_for_user(user) -> int | None:
        return getattr(user, "user_id", None) if user else None

    def user_payload(self, user) -> dict:
        entity = self.entity_store.current_for_user(self.user_id_for_user(user)) if user else None
        return {
            "userId": self.user_id_for_user(user),
            "username": self.username_for_user(user),
            "isAdmin": bool(getattr(user, "is_admin", False)),
            "canManageSystem": bool(getattr(user, "can_manage_system", False)),
            "forcePasswordChange": bool(getattr(user, "force_password_change", False)),
            "entity": entity.to_api() if entity else None,
        }

    def require_authenticated_user(self, req: Request):
        if not self.database.configured or not self.user_store.has_active_users():
            return None, None
        user = self.user_store.get_session(
            self.bearer_token_from_request(req),
            ttl_seconds=self.session_timeout_seconds(),
        )
        if not user:
            return None, JSONResponse({"error": "Authentication required."}, status_code=401)
        return user, None

    def require_admin_user(self, req: Request):
        user = self.user_store.get_session(
            self.bearer_token_from_request(req),
            ttl_seconds=self.session_timeout_seconds(),
        )
        if not user:
            return None, JSONResponse({"error": "Authentication required."}, status_code=401)
        if not user.is_admin:
            return None, JSONResponse({"error": "Admin access required."}, status_code=403)
        return user, None

    def require_system_admin_user(self, req: Request):
        user, error = self.require_authenticated_user(req)
        if error:
            return None, error
        if not getattr(user, "can_manage_system", False):
            return None, JSONResponse({"error": "System admin access required."}, status_code=403)
        return user, None

    def require_entity_member(self, req: Request):
        user, error = self.require_authenticated_user(req)
        if error:
            return None, None, error
        entity = self.entity_store.current_for_user(self.user_id_for_user(user))
        if not entity:
            return user, None, JSONResponse({"error": "No active entity membership found."}, status_code=403)
        return user, entity, None

    def require_entity_admin(self, req: Request):
        user, entity, error = self.require_entity_member(req)
        if error:
            return None, None, error
        if not entity.can_manage:
            return user, entity, JSONResponse({"error": "Entity admin access required."}, status_code=403)
        return user, entity, None
