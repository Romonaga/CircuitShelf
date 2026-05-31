from __future__ import annotations

from typing import Any

from db.connection import Database
from db.sql import load_query


class AccountProfileStore:
    def __init__(self, database: Database, logger=None):
        self.database = database
        self.logger = logger

    def get(self, user_id: int) -> dict[str, Any] | None:
        with self.database.connection() as conn:
            row = conn.execute(load_query("user_profile_get.sql"), (int(user_id),)).fetchone()
        return self._row_to_api(row)

    def update(self, user_id: int, payload: dict[str, Any]) -> dict[str, Any] | None:
        with self.database.connection() as conn:
            row = conn.execute(
                load_query("user_profile_update.sql"),
                (
                    str(payload.get("email") or "").strip(),
                    str(payload.get("displayName") or "").strip(),
                    str(payload.get("nickname") or "").strip(),
                    str(payload.get("phone") or "").strip(),
                    str(payload.get("address") or "").strip(),
                    int(user_id),
                ),
            ).fetchone()
        return self._row_to_api(row)

    @staticmethod
    def _row_to_api(row: dict[str, Any] | None) -> dict[str, Any] | None:
        if not row:
            return None
        return {
            "userId": int(row["id"]),
            "username": row["username"],
            "email": row["email"] or "",
            "displayName": row["display_name"] or "",
            "nickname": row["nickname"] or "",
            "phone": row["phone"] or "",
            "address": row["address"] or "",
            "isAdmin": bool(row["is_admin"]),
            "canManageSystem": bool(row["can_manage_system"]),
            "forcePasswordChange": bool(row["force_password_change"]),
            "passwordChangedAt": row["password_changed_at"].isoformat() if row["password_changed_at"] else None,
            "lastLoginAt": row["last_login_at"].isoformat() if row["last_login_at"] else None,
        }
