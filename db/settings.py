from __future__ import annotations

from decimal import Decimal
from typing import Any

from psycopg.errors import UndefinedTable

from db.connection import Database
from db.sql import load_query
from db.settings_catalog import SETTING_GROUPS, SETTING_UI, setting_metadata
from backend.services.settings_runtime import (
    BOOTSTRAP_SETTING_KEYS,
    DEPRECATED_SETTING_KEYS,
    SENSITIVE_SETTING_KEYS,
    setting_restart_required,
)

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

    def list_editable(self) -> list[dict[str, Any]]:
        with self.database.connection() as conn:
            rows = conn.execute(load_query("settings_admin_list.sql")).fetchall()
        settings = [self._api_row(row) for row in rows if self._is_ui_editable(row)]
        group_order = {group: index for index, group in enumerate(SETTING_GROUPS)}
        return sorted(
            settings,
            key=lambda setting: (
                group_order.get(setting["group"], len(group_order)),
                setting["advanced"],
                setting["label"].lower(),
            ),
        )

    def update_setting(self, key: str, value: Any) -> dict[str, Any]:
        with self.database.connection() as conn:
            row = conn.execute(load_query("settings_get_one.sql"), (key,)).fetchone()
            if not row:
                raise KeyError(f"Unknown setting: {key}")
            if not self._is_ui_editable(row):
                raise PermissionError(f"Setting cannot be edited from the UI: {key}")

            value_type = row["value_type"]
            typed = self._coerce_value(value_type, value)
            text_value, integer_value, numeric_value, boolean_value = self._storage_values(value_type, typed)
            conn.execute(
                load_query("settings_upsert.sql"),
                (
                    key,
                    value_type,
                    text_value,
                    integer_value,
                    numeric_value,
                    boolean_value,
                    row["description"],
                    False,
                ),
            )
            updated_row = conn.execute(load_query("settings_get_one.sql"), (key,)).fetchone()
        return self._api_row(updated_row)

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
                        key in SENSITIVE_SETTING_KEYS,
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

    def seed_setting(self, key: str, value: Any, description: str = "") -> bool:
        if not self.database.configured or key in self.load() or not self._should_store(key, value):
            return False
        value_type, text_value, integer_value, numeric_value, boolean_value = self._typed_values(value)
        with self.database.connection() as conn:
            conn.execute(
                load_query("settings_upsert.sql"),
                (key, value_type, text_value, integer_value, numeric_value, boolean_value, description, False),
            )
        return True

    def apply_to_config(self, config_wrapper) -> int:
        db_settings = self.load()
        target = getattr(config_wrapper, "config", None)
        if target is None:
            return 0
        for key, value in db_settings.items():
            if key not in BOOTSTRAP_SETTING_KEYS and key not in DEPRECATED_SETTING_KEYS:
                target[key] = value
        return len(db_settings)

    def _should_store(self, key: str, value: Any) -> bool:
        if key in BOOTSTRAP_SETTING_KEYS or key in SENSITIVE_SETTING_KEYS or key in DEPRECATED_SETTING_KEYS:
            return False
        return isinstance(value, (str, int, float, bool)) and value is not None

    def _is_ui_editable(self, row) -> bool:
        return bool(not row["is_sensitive"] and row["key"] not in BOOTSTRAP_SETTING_KEYS and row["key"] in SETTING_UI)

    def _typed_values(self, value: Any) -> tuple[str, str | None, int | None, Decimal | None, bool | None]:
        if isinstance(value, bool):
            return "boolean", None, None, None, value
        if isinstance(value, int):
            return "integer", None, value, None, None
        if isinstance(value, float):
            return "numeric", None, None, Decimal(str(value)), None
        return "text", str(value), None, None, None

    def _storage_values(self, value_type: str, value: Any) -> tuple[str | None, int | None, Decimal | None, bool | None]:
        if value_type == "boolean":
            return None, None, None, bool(value)
        if value_type == "integer":
            return None, int(value), None, None
        if value_type == "numeric":
            return None, None, Decimal(str(value)), None
        return str(value), None, None, None

    def _coerce_value(self, value_type: str, value: Any) -> Any:
        if value_type == "boolean":
            if isinstance(value, bool):
                return value
            normalized = str(value).strip().lower()
            if normalized in {"true", "1", "yes", "y", "on"}:
                return True
            if normalized in {"false", "0", "no", "n", "off"}:
                return False
            raise ValueError("Expected a boolean value.")
        if value_type == "integer":
            return int(value)
        if value_type == "numeric":
            return float(value)
        return str(value)

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

    def _api_row(self, row) -> dict[str, Any]:
        metadata = setting_metadata(row["key"]) or {}
        return {
            "key": row["key"],
            "label": metadata.get("label", row["key"].replace("_", " ").title()),
            "group": metadata.get("group", "general"),
            "groupLabel": metadata.get("groupLabel", "General"),
            "groupDescription": metadata.get("groupDescription", ""),
            "value": self._row_value(row),
            "valueType": row["value_type"],
            "description": metadata.get("description") or row["description"] or "",
            "rawDescription": row["description"] or "",
            "advanced": bool(metadata.get("advanced", False)),
            "updatedAt": row["updated_at"].isoformat() if row["updated_at"] else None,
            "restartRequired": setting_restart_required(row["key"]),
        }
