from __future__ import annotations

import secrets
from pathlib import Path
from typing import Any

import yaml

from db.connection import Database
from db.sql import load_query


class AIProviderStore:
    def __init__(self, database: Database, config_path: str | Path, logger=None):
        self.database = database
        self.config_path = Path(config_path)
        self.logger = logger

    def encryption_secret(self) -> str:
        config = self._load_config()
        secret = str(config.get("AI_KEY_ENCRYPTION_SECRET") or "")
        if secret:
            return secret
        secret = secrets.token_urlsafe(48)
        config["AI_KEY_ENCRYPTION_SECRET"] = secret
        self._save_config(config)
        return secret

    def pricing_catalog(self, provider: str = "openai") -> list[dict[str, Any]]:
        with self.database.connection() as conn:
            rows = conn.execute(load_query("ai_model_pricing_list.sql"), (provider,)).fetchall()
        return [
            {
                "provider": row["provider_code"],
                "modelName": row["model_name"],
                "inputPerMillion": float(row["input_per_million"] or 0),
                "cachedInputPerMillion": float(row["cached_input_per_million"] or 0),
                "outputPerMillion": float(row["output_per_million"] or 0),
                "currency": row["currency"],
                "isActive": bool(row["is_active"]),
                "updatedAt": row["updated_at"].isoformat() if row["updated_at"] else None,
            }
            for row in rows
        ]

    def usage_report(self, *, entity_id: int | None, days: int = 31, limit: int = 250) -> dict[str, Any]:
        with self.database.connection() as conn:
            rows = conn.execute(
                load_query("ai_assist_usage_events.sql"),
                (entity_id, entity_id, max(1, int(days)), max(1, int(limit))),
            ).fetchall()
        events = [self._usage_event_row(row) for row in rows]
        total_cost = sum(event["estimatedCost"] for event in events)
        total_tokens = sum(event["inputTokens"] + event["cachedInputTokens"] + event["outputTokens"] for event in events)
        return {
            "events": events,
            "summary": {
                "calls": len(events),
                "successfulCalls": sum(1 for event in events if event["success"]),
                "tokens": total_tokens,
                "inputTokens": sum(event["inputTokens"] for event in events),
                "cachedInputTokens": sum(event["cachedInputTokens"] for event in events),
                "outputTokens": sum(event["outputTokens"] for event in events),
                "estimatedCost": round(total_cost, 8),
            },
            "byTask": self._usage_breakdown(events, "taskLabel"),
            "byUser": self._usage_breakdown(events, "username"),
            "byPayer": self._usage_breakdown(events, "paidBy"),
            "byModel": self._usage_breakdown(events, "modelName"),
        }

    def get_system_settings(self, provider: str = "openai") -> dict[str, Any]:
        with self.database.connection() as conn:
            row = conn.execute(load_query("system_ai_provider_get.sql"), (provider,)).fetchone()
        return self._settings_row(row, scope="system", provider=provider)

    def get_entity_settings(self, entity_id: int, provider: str = "openai") -> dict[str, Any]:
        with self.database.connection() as conn:
            row = conn.execute(load_query("entity_ai_provider_get.sql"), (int(entity_id), provider)).fetchone()
        return self._settings_row(row, scope="entity", provider=provider)

    def get_user_settings(self, user_id: int, provider: str = "openai") -> dict[str, Any]:
        with self.database.connection() as conn:
            row = conn.execute(load_query("user_ai_provider_get.sql"), (int(user_id), provider)).fetchone()
        return self._settings_row(row, scope="user", provider=provider)

    def save_system_settings(self, payload: dict[str, Any], updated_by: int | None, provider: str = "openai") -> dict[str, Any]:
        ids = self._lookup_ids(provider, payload.get("assistMode") or "auto", "system")
        api_key = payload.get("apiKey")
        clear_key = bool(payload.get("clearApiKey"))
        key_value, preview, update_key = self._key_update(api_key, clear_key, self.get_system_settings(provider).get("keyPreview", ""))
        with self.database.connection() as conn:
            conn.execute(
                load_query("system_ai_provider_upsert.sql"),
                (
                    ids["provider_type_id"],
                    bool(payload.get("enabled", False)),
                    key_value,
                    key_value,
                    key_value,
                    self.encryption_secret(),
                    preview,
                    ids["assist_mode_id"],
                    str(payload.get("defaultModel") or ""),
                    updated_by,
                    update_key,
                    update_key,
                ),
            )
        return self.get_system_settings(provider)

    def save_entity_settings(self, entity_id: int, payload: dict[str, Any], updated_by: int | None, provider: str = "openai") -> dict[str, Any]:
        ids = self._lookup_ids(provider, payload.get("assistMode") or "auto", payload.get("keyPolicy") or "entity")
        current = self.get_entity_settings(entity_id, provider)
        key_value, preview, update_key = self._key_update(payload.get("apiKey"), bool(payload.get("clearApiKey")), current.get("keyPreview", ""))
        with self.database.connection() as conn:
            conn.execute(
                load_query("entity_ai_provider_upsert.sql"),
                (
                    int(entity_id),
                    ids["provider_type_id"],
                    bool(payload.get("enabled", False)),
                    key_value,
                    key_value,
                    key_value,
                    self.encryption_secret(),
                    preview,
                    ids["key_policy_id"],
                    ids["assist_mode_id"],
                    str(payload.get("defaultModel") or ""),
                    float(payload.get("monthlyBudget") or 0),
                    int(payload.get("warnPercent") or 80),
                    int(payload.get("stopPercent") or 100),
                    updated_by,
                    update_key,
                    update_key,
                ),
            )
        return self.get_entity_settings(entity_id, provider)

    def save_user_settings(self, user_id: int, payload: dict[str, Any], provider: str = "openai") -> dict[str, Any]:
        ids = self._lookup_ids(provider, payload.get("assistMode") or "auto", payload.get("keyPolicy") or "user_when_available")
        current = self.get_user_settings(user_id, provider)
        key_value, preview, update_key = self._key_update(payload.get("apiKey"), bool(payload.get("clearApiKey")), current.get("keyPreview", ""))
        with self.database.connection() as conn:
            conn.execute(
                load_query("user_ai_provider_upsert.sql"),
                (
                    int(user_id),
                    ids["provider_type_id"],
                    bool(payload.get("enabled", False)),
                    key_value,
                    key_value,
                    key_value,
                    self.encryption_secret(),
                    preview,
                    ids["key_policy_id"],
                    ids["assist_mode_id"],
                    str(payload.get("defaultModel") or ""),
                    float(payload.get("monthlyBudget") or 0),
                    int(payload.get("warnPercent") or 80),
                    int(payload.get("stopPercent") or 100),
                    update_key,
                    update_key,
                ),
            )
        return self.get_user_settings(user_id, provider)

    def _lookup_ids(self, provider: str, assist_mode: str, key_policy: str) -> dict[str, int]:
        with self.database.connection() as conn:
            row = conn.execute(load_query("ai_provider_lookups.sql"), (provider, assist_mode, key_policy)).fetchone()
        if not row or not row["provider_type_id"] or not row["assist_mode_id"] or not row["key_policy_id"]:
            raise ValueError("Unknown AI provider, assist mode, or key policy.")
        return {key: int(row[key]) for key in row.keys()}

    @staticmethod
    def _key_update(api_key: Any, clear_key: bool, current_preview: str) -> tuple[str | None, str, bool]:
        if clear_key:
            return "", "", True
        if api_key is None or str(api_key).strip() == "":
            return None, current_preview, False
        key = str(api_key).strip()
        return key, f"{key[:7]}...{key[-4:]}", True

    @staticmethod
    def _settings_row(row: dict[str, Any] | None, *, scope: str, provider: str) -> dict[str, Any]:
        if not row:
            return {
                "scope": scope,
                "provider": provider,
                "enabled": False,
                "hasApiKey": False,
                "keyPreview": "",
                "keyPolicy": "system" if scope == "system" else ("entity" if scope == "entity" else "user_when_available"),
                "assistMode": "auto",
                "defaultModel": "",
                "monthlyBudget": 0,
                "warnPercent": 80,
                "stopPercent": 100,
                "updatedAt": None,
            }
        return {
            "scope": scope,
            "provider": row["provider_code"],
            "enabled": bool(row["enabled"]),
            "hasApiKey": bool(row["key_preview"]),
            "keyPreview": row["key_preview"] or "",
            "keyPolicy": row.get("key_policy") or ("system" if scope == "system" else "entity"),
            "assistMode": row["assist_mode"],
            "defaultModel": row["default_model"] or "",
            "monthlyBudget": float(row.get("monthly_budget") or 0),
            "warnPercent": int(row.get("warn_percent") or 80),
            "stopPercent": int(row.get("stop_percent") or 100),
            "updatedAt": row["updated_at"].isoformat() if row["updated_at"] else None,
        }

    @staticmethod
    def _usage_event_row(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "createdAt": row["created_at"].isoformat() if row.get("created_at") else None,
            "entityId": row.get("entity_id"),
            "entityName": row.get("entity_name"),
            "userId": row.get("user_id"),
            "username": row.get("username") or "Unknown",
            "provider": row.get("provider") or "unknown",
            "taskType": row.get("task_type") or "unknown",
            "taskLabel": row.get("task_label") or "Unknown",
            "modelName": row.get("model_name") or "Unknown",
            "contextType": row.get("context_type") or "",
            "contextId": str(row.get("context_id")) if row.get("context_id") else "",
            "roundNumber": int(row.get("round_number") or 1),
            "roundCount": int(row.get("round_count") or 1),
            "inputTokens": int(row.get("input_tokens") or 0),
            "cachedInputTokens": int(row.get("cached_input_tokens") or 0),
            "outputTokens": int(row.get("output_tokens") or 0),
            "estimatedCost": float(row.get("estimated_cost") or 0),
            "paidBy": row.get("paid_by") or "unknown",
            "providerKeyOwnerUserId": row.get("provider_key_owner_user_id"),
            "providerKeyOwnerUsername": row.get("provider_key_owner_username"),
            "success": bool(row.get("success")),
            "errorMessage": row.get("error_message"),
        }

    @staticmethod
    def _usage_breakdown(events: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
        grouped: dict[str, dict[str, Any]] = {}
        for event in events:
            label = str(event.get(key) or "Unknown")
            current = grouped.setdefault(label, {"label": label, "calls": 0, "tokens": 0, "estimatedCost": 0.0})
            current["calls"] += 1
            current["tokens"] += int(event.get("inputTokens") or 0) + int(event.get("cachedInputTokens") or 0) + int(event.get("outputTokens") or 0)
            current["estimatedCost"] += float(event.get("estimatedCost") or 0)
        return sorted(
            ({**value, "estimatedCost": round(value["estimatedCost"], 8)} for value in grouped.values()),
            key=lambda item: item["estimatedCost"],
            reverse=True,
        )

    def _load_config(self) -> dict:
        with open(self.config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def _save_config(self, config: dict) -> None:
        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(config, f, sort_keys=False)
