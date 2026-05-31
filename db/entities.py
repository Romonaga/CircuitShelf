from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from db.connection import Database
from db.sql import load_query


@dataclass(frozen=True)
class EntityContext:
    entity_id: int
    name: str
    slug: str
    role: str
    role_name: str
    can_manage: bool
    owner_user_id: int | None

    def to_api(self) -> dict[str, Any]:
        return {
            "id": self.entity_id,
            "name": self.name,
            "slug": self.slug,
            "role": self.role,
            "roleName": self.role_name,
            "canManage": self.can_manage,
            "ownerUserId": self.owner_user_id,
        }


def slugify_entity_name(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(name or "").strip().lower()).strip("-")
    return slug or "entity"


class EntityStore:
    def __init__(self, database: Database, logger=None):
        self.database = database
        self.logger = logger

    def current_for_user(self, user_id: int | None) -> EntityContext | None:
        if not user_id:
            return None
        with self.database.connection() as conn:
            row = conn.execute(load_query("entity_current_for_user.sql"), (int(user_id),)).fetchone()
        return self._row_to_context(row)

    def memberships_for_user(self, user_id: int | None) -> list[EntityContext]:
        if not user_id:
            return []
        with self.database.connection() as conn:
            rows = conn.execute(load_query("entity_memberships_for_user.sql"), (int(user_id),)).fetchall()
        return [ctx for row in rows if (ctx := self._row_to_context(row))]

    def members(self, entity_id: int) -> list[dict[str, Any]]:
        with self.database.connection() as conn:
            rows = conn.execute(load_query("entity_members_list.sql"), (int(entity_id),)).fetchall()
        return [
            {
                "userId": int(row["user_id"]),
                "username": row["username"],
                "email": row["email"],
                "displayName": row["display_name"],
                "nickname": row["nickname"],
                "isActive": bool(row["is_active"]),
                "canManageSystem": bool(row["can_manage_system"]),
                "role": row["role_code"],
                "roleName": row["role_name"],
                "canManage": bool(row["can_manage_entity"]),
                "createdAt": row["created_at"].isoformat() if row["created_at"] else None,
                "updatedAt": row["updated_at"].isoformat() if row["updated_at"] else None,
            }
            for row in rows
        ]

    def upsert_entity(self, name: str, owner_user_id: int | None = None) -> dict[str, Any]:
        slug = slugify_entity_name(name)
        with self.database.connection() as conn:
            row = conn.execute(load_query("entity_upsert_by_slug.sql"), (name, slug, owner_user_id)).fetchone()
        return dict(row)

    def upsert_membership(self, entity_id: int, user_id: int, role: str) -> None:
        with self.database.connection() as conn:
            conn.execute(load_query("entity_membership_upsert.sql"), (int(entity_id), int(user_id), role))

    def set_system_privileges(self, username: str, *, can_manage_system: bool, is_admin: bool) -> dict[str, Any] | None:
        with self.database.connection() as conn:
            row = conn.execute(
                load_query("user_system_privileges_update.sql"),
                (can_manage_system, is_admin, can_manage_system, username),
            ).fetchone()
        return dict(row) if row else None

    def ensure_default_entity(self, name: str, owner_username: str, member_roles: dict[str, str]) -> dict[str, Any]:
        with self.database.connection() as conn:
            owner = conn.execute(load_query("users_find_id_by_username.sql"), (owner_username,)).fetchone()
            if not owner:
                raise ValueError(f"Owner user does not exist: {owner_username}")
            entity = conn.execute(load_query("entity_upsert_by_slug.sql"), (name, slugify_entity_name(name), owner["id"])).fetchone()
            for username, role in member_roles.items():
                user = conn.execute(load_query("users_find_id_by_username.sql"), (username,)).fetchone()
                if user:
                    conn.execute(load_query("entity_membership_upsert.sql"), (entity["id"], user["id"], role))
        return dict(entity)

    @staticmethod
    def _row_to_context(row: dict[str, Any] | None) -> EntityContext | None:
        if not row:
            return None
        return EntityContext(
            entity_id=int(row["entity_id"]),
            name=str(row["entity_name"]),
            slug=str(row["entity_slug"]),
            role=str(row["role_code"]),
            role_name=str(row["role_name"]),
            can_manage=bool(row["can_manage_entity"]),
            owner_user_id=int(row["owner_user_id"]) if row["owner_user_id"] is not None else None,
        )
