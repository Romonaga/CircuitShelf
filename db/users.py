from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass

import bcrypt
from psycopg.errors import UndefinedTable

from db.connection import Database
from db.sql import load_query


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: int
    username: str
    is_admin: bool


@dataclass(frozen=True)
class UserSession:
    token: str
    user_id: int
    username: str
    is_admin: bool


class UserStore:
    def __init__(self, database: Database, logger=None):
        self.database = database
        self.logger = logger

    def has_active_users(self) -> bool:
        if not self.database.configured:
            return False
        try:
            with self.database.connection() as conn:
                row = conn.execute(load_query("users_exists_active.sql")).fetchone()
            return bool(row and row["has_users"])
        except UndefinedTable:
            return False
        except Exception as exc:
            if self.logger:
                self.logger.warning(f"Unable to check DB users: {exc}")
            return False

    def verify_user(self, username: str, password: str) -> AuthenticatedUser | None:
        if not username or not password or not self.database.configured:
            return None

        try:
            with self.database.connection() as conn:
                row = conn.execute(load_query("users_find_for_login.sql"), (username,)).fetchone()

                if not row:
                    return None

                stored_hash = row["password_hash"]
                if not bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8")):
                    return None

                conn.execute(load_query("users_touch_last_login.sql"), (username,))
                return AuthenticatedUser(user_id=int(row["id"]), username=str(row["username"]), is_admin=bool(row["is_admin"]))
        except UndefinedTable:
            if self.logger:
                self.logger.warning("Users table does not exist. Run database migrations before logging in.")
            return None
        except Exception as exc:
            if self.logger:
                self.logger.error(f"Database login failed: {exc}")
            return None

    def upsert_user(
        self,
        username: str,
        password: str,
        *,
        is_admin: bool = False,
        is_active: bool = True,
    ) -> None:
        password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        with self.database.connection() as conn:
            conn.execute(
                load_query("users_upsert.sql"),
                (username, password_hash, is_admin, is_active),
            )

    def change_password(self, user_id: int, current_password: str, new_password: str) -> bool:
        if not current_password or not new_password or len(new_password) < 8:
            return False

        with self.database.connection() as conn:
            row = conn.execute(load_query("users_find_by_id.sql"), (int(user_id),)).fetchone()
            if not row:
                return False
            stored_hash = row["password_hash"]
            if not bcrypt.checkpw(current_password.encode("utf-8"), stored_hash.encode("utf-8")):
                return False
            password_hash = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
            conn.execute(load_query("users_update_password.sql"), (password_hash, int(user_id)))
        return True

    def list_users(self) -> list[dict]:
        with self.database.connection() as conn:
            rows = conn.execute(load_query("users_list.sql")).fetchall()
        return [dict(row) for row in rows]

    def create_session(self, user: AuthenticatedUser, ttl_seconds: int = 604800) -> UserSession:
        token = secrets.token_urlsafe(32)
        token_hash = self._token_hash(token)
        with self.database.connection() as conn:
            conn.execute(load_query("user_sessions_prune.sql"))
            conn.execute(load_query("user_sessions_insert.sql"), (user.user_id, user.username, token_hash, int(ttl_seconds)))
        return UserSession(token=token, user_id=user.user_id, username=user.username, is_admin=user.is_admin)

    def get_session(self, token: str, *, ttl_seconds: int | None = None) -> AuthenticatedUser | None:
        if not token:
            return None
        token_hash = self._token_hash(token)
        try:
            with self.database.connection() as conn:
                row = conn.execute(load_query("user_sessions_find.sql"), (token_hash,)).fetchone()
                if not row:
                    return None
                ttl = int(ttl_seconds or 0)
                if ttl > 0:
                    conn.execute(load_query("user_sessions_touch.sql"), (ttl, token_hash))
            return AuthenticatedUser(user_id=int(row["id"]), username=str(row["username"]), is_admin=bool(row["is_admin"]))
        except Exception as exc:
            if self.logger:
                self.logger.warning(f"Session lookup failed: {exc}")
            return None

    def delete_session(self, token: str) -> None:
        if not token:
            return
        with self.database.connection() as conn:
            conn.execute(load_query("user_sessions_delete.sql"), (self._token_hash(token),))

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()
