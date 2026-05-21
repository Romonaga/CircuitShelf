from __future__ import annotations

from dataclasses import dataclass

import bcrypt
from psycopg.errors import UndefinedTable

from db.connection import Database
from db.sql import load_query


@dataclass(frozen=True)
class AuthenticatedUser:
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
                return AuthenticatedUser(username=str(row["username"]), is_admin=bool(row["is_admin"]))
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

    def list_users(self) -> list[dict]:
        with self.database.connection() as conn:
            rows = conn.execute(load_query("users_list.sql")).fetchall()
        return [dict(row) for row in rows]
