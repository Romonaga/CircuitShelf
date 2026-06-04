from __future__ import annotations

from dataclasses import dataclass
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
    "EXTRACTED_IMAGES_DIR",
    "SAVE_EXTRACTED_IMAGES",
}

RESTART_REQUIRED_SETTING_KEYS = BOOTSTRAP_SETTING_KEYS | {
    "API_HOST",
    "API_PORT",
    "APP_HOST",
    "APP_PORT",
    "BYPASS_NLTK_DOWNLOAD",
    "CROSS_ENCODER_MODEL",
    "EMBED_MODEL_NAME",
    "MODEL_DEVICE",
    "NLTK_DATA_DIR",
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
        self._callbacks: dict[str, Callable[[Any], None]] = {}

    def register_callback(self, key: str, callback: Callable[[Any], None]) -> None:
        self._callbacks[key] = callback

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
        callback = self._callbacks.get(key)
        if callback:
            callback(value)
            applied = True
        return applied or not setting_restart_required(key)
