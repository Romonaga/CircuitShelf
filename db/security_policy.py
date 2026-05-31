from __future__ import annotations

from typing import Any

from db.connection import Database
from db.sql import load_query


class PasswordPolicyStore:
    def __init__(self, database: Database, logger=None):
        self.database = database
        self.logger = logger

    def effective_policy(self, entity_id: int | None = None) -> dict[str, Any]:
        with self.database.connection() as conn:
            row = conn.execute(load_query("password_policy_get_effective.sql"), (entity_id,)).fetchone()
        return self._row_to_api(row)

    def upsert_policy(self, entity_id: int | None, payload: dict[str, Any], updated_by: int | None) -> dict[str, Any]:
        current = self.effective_policy(entity_id)
        values = {
            "minLength": payload.get("minLength", current["minLength"]),
            "requireUpper": payload.get("requireUpper", current["requireUpper"]),
            "requireLower": payload.get("requireLower", current["requireLower"]),
            "requireNumber": payload.get("requireNumber", current["requireNumber"]),
            "requireSymbol": payload.get("requireSymbol", current["requireSymbol"]),
            "passwordChangeDays": payload.get("passwordChangeDays", current["passwordChangeDays"]),
            "maxFailedAttempts": payload.get("maxFailedAttempts", current["maxFailedAttempts"]),
            "lockoutMinutes": payload.get("lockoutMinutes", current["lockoutMinutes"]),
        }
        with self.database.connection() as conn:
            row = conn.execute(
                load_query("password_policy_upsert.sql"),
                (
                    entity_id,
                    int(values["minLength"]),
                    bool(values["requireUpper"]),
                    bool(values["requireLower"]),
                    bool(values["requireNumber"]),
                    bool(values["requireSymbol"]),
                    int(values["passwordChangeDays"]),
                    int(values["maxFailedAttempts"]),
                    int(values["lockoutMinutes"]),
                    updated_by,
                ),
            ).fetchone()
        return self._row_to_api(row)

    @staticmethod
    def _row_to_api(row: dict[str, Any] | None) -> dict[str, Any]:
        if not row:
            return {
                "entityId": None,
                "minLength": 12,
                "requireUpper": True,
                "requireLower": True,
                "requireNumber": True,
                "requireSymbol": False,
                "passwordChangeDays": 0,
                "maxFailedAttempts": 5,
                "lockoutMinutes": 30,
                "updatedAt": None,
            }
        return {
            "id": int(row["id"]),
            "entityId": int(row["entity_id"]) if row["entity_id"] is not None else None,
            "minLength": int(row["min_length"]),
            "requireUpper": bool(row["require_upper"]),
            "requireLower": bool(row["require_lower"]),
            "requireNumber": bool(row["require_number"]),
            "requireSymbol": bool(row["require_symbol"]),
            "passwordChangeDays": int(row["password_change_days"]),
            "maxFailedAttempts": int(row["max_failed_attempts"]),
            "lockoutMinutes": int(row["lockout_minutes"]),
            "updatedAt": row["updated_at"].isoformat() if row.get("updated_at") else None,
        }
