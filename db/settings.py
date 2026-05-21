from __future__ import annotations

from decimal import Decimal
from typing import Any

from psycopg.errors import UndefinedTable

from db.connection import Database
from db.sql import load_query


BOOTSTRAP_KEYS = {
    "DATABASE_URL",
    "DB_MIGRATIONS_DIR",
    "DB_SCHEMA_VERSION_TABLE",
    "TRACE_LOG_FILE",
    "TRACE_ROTATE",
    "TRACE_MAX_BYTES",
    "TRACE_BACKUP_COUNT",
    "TRACE_WHEN",
    "TRACE_TIMESTAMPED_NAME",
    "TRACE_LOG_LEVEL",
}

SENSITIVE_KEYS = {
    "DATABASE_URL",
    "LLM_API_KEY",
}

class AppSettingsStore:
    def __init__(self, database: Database, logger=None):
        self.database = database
        self.logger = logger

    def load(self) -> dict[str, Any]:
        if not self.database.configured:
            return {}
        try:
            with self.database.connection() as conn:
                rows = conn.execute(load_query("settings_list.sql")).fetchall()
        except UndefinedTable:
            return {}
        return {row["key"]: self._row_value(row) for row in rows}

    def seed_from_config(self, config: dict[str, Any]) -> int:
        if not self.database.configured:
            return 0

        existing = self.load()
        seeded = 0
        with self.database.connection() as conn:
            for key, value in sorted(config.items()):
                if key in existing or not self._should_store(key, value):
                    continue
                value_type, text_value, integer_value, numeric_value, boolean_value = self._typed_values(value)
                conn.execute(
                    load_query("settings_upsert.sql"),
                    (
                        key,
                        value_type,
                        text_value,
                        integer_value,
                        numeric_value,
                        boolean_value,
                        f"Imported from bootstrap config for {key}.",
                        key in SENSITIVE_KEYS,
                    ),
                )
                seeded += 1
        return seeded

    def seed_text_setting(self, key: str, value: str, description: str = "") -> bool:
        if not self.database.configured or key in self.load():
            return False
        with self.database.connection() as conn:
            conn.execute(
                load_query("settings_upsert.sql"),
                (key, "text", value, None, None, None, description, False),
            )
        return True

    def apply_to_config(self, config_wrapper) -> int:
        db_settings = self.load()
        target = getattr(config_wrapper, "config", None)
        if target is None:
            return 0
        for key, value in db_settings.items():
            if key not in BOOTSTRAP_KEYS:
                target[key] = value
        return len(db_settings)

    def _should_store(self, key: str, value: Any) -> bool:
        if key in BOOTSTRAP_KEYS or key in SENSITIVE_KEYS:
            return False
        return isinstance(value, (str, int, float, bool)) and value is not None

    def _typed_values(self, value: Any) -> tuple[str, str | None, int | None, Decimal | None, bool | None]:
        if isinstance(value, bool):
            return "boolean", None, None, None, value
        if isinstance(value, int):
            return "integer", None, value, None, None
        if isinstance(value, float):
            return "numeric", None, None, Decimal(str(value)), None
        return "text", str(value), None, None, None

    @staticmethod
    def _row_value(row) -> Any:
        value_type = row["value_type"]
        if value_type == "boolean":
            return bool(row["boolean_value"])
        if value_type == "integer":
            return int(row["integer_value"])
        if value_type == "numeric":
            return float(row["numeric_value"])
        return row["text_value"]
