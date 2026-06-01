from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone

import bcrypt
from psycopg.errors import UndefinedTable, UniqueViolation

from db.connection import Database
from db.sql import load_query


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: int
    username: str
    is_admin: bool
    can_manage_system: bool = False
    force_password_change: bool = False


@dataclass(frozen=True)
class UserSession:
    token: str
    user_id: int
    username: str
    is_admin: bool
    can_manage_system: bool = False
    force_password_change: bool = False


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
                row = conn.execute(load_query("users_find_for_login_full.sql"), (username,)).fetchone()

                if not row:
                    return None
                policy = self._effective_policy_for_user(conn, int(row["id"]))
                if not row["is_active"] or row["disabled_at"] is not None:
                    return None

                stored_hash = row["password_hash"]
                if not bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8")):
                    conn.execute(
                        load_query("users_login_failure_update.sql"),
                        (
                            int(policy["max_failed_attempts"]),
                            int(policy["max_failed_attempts"]),
                            int(row["id"]),
                        ),
                    )
                    return None

                conn.execute(load_query("users_login_success_update.sql"), (int(row["id"]),))
                force_change = bool(row.get("force_password_change")) or self._password_expired(row, policy)
                return AuthenticatedUser(
                    user_id=int(row["id"]),
                    username=str(row["username"]),
                    is_admin=bool(row["is_admin"]),
                    can_manage_system=bool(row.get("can_manage_system")),
                    force_password_change=force_change,
                )
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

    def create_user(
        self,
        *,
        username: str,
        password: str,
        email: str = "",
        display_name: str = "",
        nickname: str = "",
        phone: str = "",
        address: str = "",
        is_admin: bool = False,
        force_password_change: bool = True,
    ) -> dict:
        clean_username = str(username or "").strip()
        if not clean_username:
            raise ValueError("Username is required.")
        if not password:
            raise ValueError("Temporary password is required.")
        password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        try:
            with self.database.connection() as conn:
                row = conn.execute(
                    load_query("users_create.sql"),
                    (
                        clean_username,
                        password_hash,
                        bool(is_admin),
                        str(email or "").strip(),
                        str(display_name or "").strip(),
                        str(nickname or "").strip(),
                        str(phone or "").strip(),
                        str(address or "").strip(),
                        bool(force_password_change),
                    ),
                ).fetchone()
        except UniqueViolation as exc:
            raise ValueError("Username or email already exists.") from exc
        return dict(row)

    def reset_password(self, user_id: int, new_password: str, *, force_password_change: bool = True) -> dict | None:
        if not new_password:
            raise ValueError("Temporary password is required.")
        password_hash = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        with self.database.connection() as conn:
            row = conn.execute(
                load_query("users_admin_password_reset.sql"),
                (password_hash, bool(force_password_change), int(user_id)),
            ).fetchone()
        return dict(row) if row else None

    def change_password(self, user_id: int, current_password: str, new_password: str) -> bool:
        if not current_password or not new_password:
            return False

        with self.database.connection() as conn:
            row = conn.execute(load_query("users_find_by_id.sql"), (int(user_id),)).fetchone()
            if not row:
                return False
            policy = self._effective_policy_for_user(conn, int(user_id))
            if self.password_policy_issues(new_password, policy):
                return False
            stored_hash = row["password_hash"]
            if not bcrypt.checkpw(current_password.encode("utf-8"), stored_hash.encode("utf-8")):
                return False
            password_hash = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
            conn.execute(load_query("users_update_password.sql"), (password_hash, int(user_id)))
        return True

    def password_policy_for_user(self, user_id: int) -> dict:
        with self.database.connection() as conn:
            return dict(self._effective_policy_for_user(conn, int(user_id)))

    @staticmethod
    def password_policy_issues(password: str, policy: dict) -> list[str]:
        issues = []
        if len(password or "") < int(policy["min_length"]):
            issues.append(f"Password must be at least {int(policy['min_length'])} characters.")
        if policy["require_upper"] and not any(ch.isupper() for ch in password):
            issues.append("Password must include an uppercase letter.")
        if policy["require_lower"] and not any(ch.islower() for ch in password):
            issues.append("Password must include a lowercase letter.")
        if policy["require_number"] and not any(ch.isdigit() for ch in password):
            issues.append("Password must include a number.")
        if policy["require_symbol"] and not any(not ch.isalnum() for ch in password):
            issues.append("Password must include a symbol.")
        return issues

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
        return UserSession(
            token=token,
            user_id=user.user_id,
            username=user.username,
            is_admin=user.is_admin,
            can_manage_system=user.can_manage_system,
            force_password_change=user.force_password_change,
        )

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
            return AuthenticatedUser(
                user_id=int(row["id"]),
                username=str(row["username"]),
                is_admin=bool(row["is_admin"]),
                can_manage_system=bool(row.get("can_manage_system")),
                force_password_change=bool(row.get("force_password_change")),
            )
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

    def _effective_policy_for_user(self, conn, user_id: int) -> dict:
        entity_row = conn.execute(load_query("users_entity_id_for_policy.sql"), (int(user_id),)).fetchone()
        entity_id = entity_row["entity_id"] if entity_row else None
        policy = conn.execute(load_query("password_policy_get_effective.sql"), (entity_id,)).fetchone()
        return dict(policy) if policy else {
            "min_length": 12,
            "require_upper": True,
            "require_lower": True,
            "require_number": True,
            "require_symbol": False,
            "password_change_days": 0,
            "max_failed_attempts": 5,
            "lockout_minutes": 30,
        }

    @staticmethod
    def _password_expired(row: dict, policy: dict) -> bool:
        days = int(policy.get("password_change_days") or 0)
        changed_at = row.get("password_changed_at")
        if days <= 0 or not changed_at:
            return False
        if changed_at.tzinfo is None:
            changed_at = changed_at.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - changed_at).days >= days
