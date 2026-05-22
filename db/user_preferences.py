from __future__ import annotations

import json
from typing import Any

from psycopg.errors import UndefinedTable

from db.connection import Database
from db.sql import load_query


class UserPreferencesStore:
    def __init__(self, database: Database, logger=None):
        self.database = database
        self.logger = logger

    def available(self) -> bool:
        if not self.database.configured:
            return False
        try:
            with self.database.connection() as conn:
                conn.execute(load_query("user_preference_get.sql"), (0, "__probe__")).fetchone()
            return True
        except UndefinedTable:
            return False
        except Exception as exc:
            if self.logger:
                self.logger.warning(f"User preferences store is not available: {exc}")
            return False

    def get(self, user_id: int | None, key: str, default: Any = None) -> Any:
        if not user_id:
            return default
        with self.database.connection() as conn:
            row = conn.execute(load_query("user_preference_get.sql"), (int(user_id), key)).fetchone()
        if not row:
            return default
        return row["preference_value"]

    def set(self, user_id: int, key: str, value: Any) -> Any:
        with self.database.connection() as conn:
            row = conn.execute(
                load_query("user_preference_upsert.sql"),
                (int(user_id), key, json.dumps(value)),
            ).fetchone()
        return row["preference_value"]
