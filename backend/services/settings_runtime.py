from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Iterable
from typing import Any, Callable, Mapping


BOOTSTRAP_SETTING_KEYS = {
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

SENSITIVE_SETTING_KEYS = {
    "DATABASE_URL",
    "LLM_API_KEY",
}

DEPRECATED_SETTING_KEYS = {
    "API_HOST",
    "API_PORT",
    "EXTRACTED_IMAGES_DIR",
    "BYPASS_NLTK_DOWNLOAD",
    "LRU_CACHE_SIZE",
    "NLTK_DATA_DIR",
    "SAVE_EXTRACTED_IMAGES",
}

RESTART_REQUIRED_SETTING_KEYS = BOOTSTRAP_SETTING_KEYS | {
    "APP_HOST",
    "APP_PORT",
    "CROSS_ENCODER_MODEL",
    "EMBED_MODEL_NAME",
    "MODEL_DEVICE",
    "REACT_DIST_DIR",
    "RESPONSE_CACHE_CAPACITY",
    "TESSERACT_CMD",
    "TRAINING_DIR",
}


def setting_restart_required(key: str) -> bool:
    return key in RESTART_REQUIRED_SETTING_KEYS


@dataclass(frozen=True)
class SettingChange:
    key: str
    old_value: Any
    new_value: Any
    changed: bool
    runtime_applied: bool
    restart_required: bool


class RuntimeSettingsManager:
    def __init__(self, config_wrapper, module_globals: dict[str, Any] | None = None, logger=None):
        self.config_wrapper = config_wrapper
        self.module_globals = module_globals if module_globals is not None else {}
        self.logger = logger
        self._callbacks: dict[str, list[Callable[[Any], None]]] = {}
        self._config_live_keys: set[str] = set()

    def register_callback(self, key: str, callback: Callable[[Any], None]) -> None:
        self._callbacks.setdefault(key, []).append(callback)

    def register_refresh_callback(self, keys: Iterable[str], callback: Callable[[str, Any], None]) -> None:
        for key in keys:
            self.register_callback(key, lambda value, setting_key=key: callback(setting_key, value))

    def register_config_live_keys(self, keys: Iterable[str]) -> None:
        self._config_live_keys.update(keys)

    def apply_update(self, key: str, value: Any) -> SettingChange:
        target = getattr(self.config_wrapper, "config", None)
        old_value = target.get(key) if isinstance(target, dict) else None
        changed = old_value != value
        restart_required = setting_restart_required(key)

        if isinstance(target, dict):
            target[key] = value

        runtime_applied = False
        if not restart_required:
            runtime_applied = self._apply_live_value(key, value)

        return SettingChange(
            key=key,
            old_value=old_value,
            new_value=value,
            changed=changed,
            runtime_applied=runtime_applied,
            restart_required=restart_required,
        )

    def apply_updates(self, values: Mapping[str, Any]) -> list[SettingChange]:
        changes = []
        for key, value in values.items():
            change = self.apply_update(key, value)
            if change.changed:
                changes.append(change)
        return changes

    def refresh_from_store(self, settings_store) -> list[SettingChange]:
        return self.apply_updates(settings_store.load())

    def _apply_live_value(self, key: str, value: Any) -> bool:
        applied = False
        if key in self.module_globals:
            self.module_globals[key] = value
            applied = True
        for callback in self._callbacks.get(key, []):
            callback(value)
            applied = True
        if key in self._config_live_keys:
            applied = True
        return applied
