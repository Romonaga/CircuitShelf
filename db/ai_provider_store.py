from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID
import json

from db.ai_key_secret import load_ai_key_encryption_secret
from db.connection import Database
from db.sql import load_query


class AIProviderStore:
    def __init__(self, database: Database, config_path: str | Path, logger=None):
        self.database = database
        self.config_path = Path(config_path)
        self.logger = logger

    def encryption_secret(self) -> str:
        return load_ai_key_encryption_secret(config_path=self.config_path, logger=self.logger)

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

    def pricing_variants(self, provider: str = "openai") -> list[dict[str, Any]]:
        with self.database.connection() as conn:
            rows = conn.execute(load_query("ai_model_pricing_variants_list.sql"), (provider,)).fetchall()
        return [
            {
                "provider": row["provider_code"],
                "modelName": row["model_name"],
                "contextBand": row["context_band"],
                "serviceTier": row["service_tier"],
                "inputPerMillion": float(row["input_per_million"] or 0),
                "cachedInputPerMillion": float(row["cached_input_per_million"] or 0),
                "outputPerMillion": float(row["output_per_million"] or 0),
                "currency": row["currency"],
                "sourceNote": row["source_note"],
                "isActive": bool(row["is_active"]),
                "updatedAt": row["updated_at"].isoformat() if row["updated_at"] else None,
            }
            for row in rows
        ]

    def pricing_for_model(
        self,
        model_name: str,
        provider: str = "openai",
        *,
        billing_scope: str = "system",
        entity_id: int | None = None,
        user_id: int | None = None,
    ) -> dict[str, Any]:
        with self.database.connection() as conn:
            row = conn.execute(
                load_query("ai_model_pricing_resolve.sql"),
                (
                    provider,
                    model_name,
                    billing_scope,
                    billing_scope,
                    billing_scope,
                    entity_id,
                    billing_scope,
                    user_id,
                ),
            ).fetchone()
        if not row:
            return {
                "provider": provider,
                "modelName": model_name,
                "inputPerMillion": 0.0,
                "cachedInputPerMillion": 0.0,
                "outputPerMillion": 0.0,
                "currency": "USD",
                "isOverride": False,
            }
        return {
            "provider": row["provider_code"],
            "modelName": row["model_name"],
            "inputPerMillion": float(row["input_per_million"] or 0),
            "cachedInputPerMillion": float(row["cached_input_per_million"] or 0),
            "outputPerMillion": float(row["output_per_million"] or 0),
            "currency": row["currency"],
            "isOverride": bool(row.get("is_override")),
        }

    def pricing_overrides(
        self,
        *,
        scope: str,
        provider: str = "openai",
        entity_id: int | None = None,
        user_id: int | None = None,
    ) -> list[dict[str, Any]]:
        with self.database.connection() as conn:
            rows = conn.execute(
                load_query("ai_model_pricing_overrides_list.sql"),
                (provider, scope, entity_id, entity_id, user_id, user_id),
            ).fetchall()
        return [
            {
                "provider": row["provider_code"],
                "modelName": row["model_name"],
                "scope": row["scope"],
                "entityId": row.get("entity_id"),
                "userId": row.get("user_id"),
                "inputPerMillion": float(row["input_per_million"] or 0),
                "cachedInputPerMillion": float(row["cached_input_per_million"] or 0),
                "outputPerMillion": float(row["output_per_million"] or 0),
                "currency": row["currency"],
                "updatedAt": row["updated_at"].isoformat() if row["updated_at"] else None,
            }
            for row in rows
        ]

    def save_pricing_overrides(
        self,
        *,
        scope: str,
        overrides: list[dict[str, Any]],
        provider: str = "openai",
        entity_id: int | None = None,
        user_id: int | None = None,
        updated_by: int | None = None,
    ) -> None:
        with self.database.connection() as conn:
            conn.execute(
                load_query("ai_model_pricing_override_delete_scope.sql"),
                (provider, scope, entity_id, entity_id, user_id, user_id),
            )
            for override in overrides or []:
                model_name = str(override.get("modelName") or "").strip()
                if not model_name:
                    continue
                conn.execute(
                    load_query("ai_model_pricing_override_upsert.sql"),
                    (
                        provider,
                        model_name,
                        scope,
                        entity_id if scope == "entity" else None,
                        user_id if scope == "user" else None,
                        max(0.0, float(override.get("inputPerMillion") or 0)),
                        max(0.0, float(override.get("cachedInputPerMillion") or 0)),
                        max(0.0, float(override.get("outputPerMillion") or 0)),
                        str(override.get("currency") or "USD"),
                        updated_by,
                    ),
                )

    def estimate_cost(
        self,
        *,
        provider: str,
        model_name: str,
        input_tokens: int,
        cached_input_tokens: int = 0,
        output_tokens: int = 0,
        billing_scope: str = "system",
        entity_id: int | None = None,
        user_id: int | None = None,
    ) -> float:
        pricing = self.pricing_for_model(
            model_name,
            provider,
            billing_scope=billing_scope,
            entity_id=entity_id,
            user_id=user_id,
        )
        regular_input_tokens = max(0, int(input_tokens or 0) - int(cached_input_tokens or 0))
        cost = (
            regular_input_tokens * pricing["inputPerMillion"]
            + int(cached_input_tokens or 0) * pricing["cachedInputPerMillion"]
            + int(output_tokens or 0) * pricing["outputPerMillion"]
        ) / 1_000_000
        return round(float(cost), 8)

    def monthly_spend_for_scope(
        self,
        *,
        billing_scope: str,
        entity_id: int | None = None,
        user_id: int | None = None,
    ) -> float:
        scope = str(billing_scope or "system")
        with self.database.connection() as conn:
            row = conn.execute(
                load_query("ai_assist_monthly_spend.sql"),
                (
                    scope,
                    scope,
                    scope,
                    entity_id,
                    scope,
                    user_id,
                ),
            ).fetchone()
        return float((row or {}).get("estimated_cost") or 0)

    def budget_status_for_settings(self, settings: dict[str, Any]) -> dict[str, Any]:
        monthly_budget = float(settings.get("monthlyBudget") or 0)
        stop_percent = int(settings.get("stopPercent") or 100)
        warn_percent = int(settings.get("warnPercent") or 80)
        spend = self.monthly_spend_for_scope(
            billing_scope=settings.get("pricingScope") or settings.get("paidBy") or "system",
            entity_id=settings.get("pricingEntityId"),
            user_id=settings.get("pricingUserId"),
        )
        stop_at = monthly_budget * max(1, stop_percent) / 100 if monthly_budget > 0 else 0
        warn_at = monthly_budget * max(1, warn_percent) / 100 if monthly_budget > 0 else 0
        return {
            "monthlyBudget": monthly_budget,
            "monthSpend": round(spend, 8),
            "warnAt": round(warn_at, 8),
            "stopAt": round(stop_at, 8),
            "warned": bool(monthly_budget > 0 and spend >= warn_at),
            "blocked": bool(monthly_budget > 0 and spend >= stop_at),
        }

    def resolve_openai_assist(
        self,
        *,
        entity_id: int | None,
        user_id: int | None,
        default_model: str = "gpt-5-chat-latest",
    ) -> dict[str, Any] | None:
        system = self._secret_row("system", provider="openai")
        entity = self._secret_row("entity", entity_id=entity_id, provider="openai") if entity_id else None
        user = self._secret_row("user", user_id=user_id, provider="openai") if user_id else None

        def usable(row: dict[str, Any] | None) -> bool:
            return bool(row and row.get("enabled") and row.get("apiKey") and row.get("assistMode") != "off")

        entity_policy = (entity or {}).get("keyPolicy") or "entity"
        user_policy = (user or {}).get("keyPolicy") or "user_when_available"

        if usable(user) and user_policy in {"user_when_available", "user_only"}:
            return self._resolved_provider(row=user, paid_by="user", owner_user_id=user_id, default_model=default_model, entity_id=entity_id, user_id=user_id)
        if entity_policy == "user_only":
            return None
        if usable(entity) and entity_policy in {"entity", "user_when_available"}:
            return self._resolved_provider(row=entity, paid_by="entity", owner_user_id=None, default_model=default_model, entity_id=entity_id, user_id=None)
        if usable(system):
            return self._resolved_provider(row=system, paid_by="system", owner_user_id=None, default_model=default_model, entity_id=None, user_id=None)
        return None

    def resolve_openai_ingestion_assist(
        self,
        *,
        is_global: bool,
        entity_id: int | None,
        user_id: int | None,
        default_model: str = "gpt-5-chat-latest",
    ) -> dict[str, Any] | None:
        system = self._secret_row("system", provider="openai")

        def usable(row: dict[str, Any] | None) -> bool:
            return bool(row and row.get("enabled") and row.get("apiKey") and row.get("assistMode") != "off")

        if is_global:
            return self._resolved_provider(row=system, paid_by="system", owner_user_id=None, default_model=default_model, entity_id=None, user_id=None) if usable(system) else None

        entity = self._secret_row("entity", entity_id=entity_id, provider="openai") if entity_id else None
        if usable(entity):
            return self._resolved_provider(row=entity, paid_by="entity", owner_user_id=None, default_model=default_model, entity_id=entity_id, user_id=None)

        user = self._secret_row("user", user_id=user_id, provider="openai") if user_id else None
        user_policy = (user or {}).get("keyPolicy") or "user_when_available"
        if usable(user) and user_policy in {"user_when_available", "user_only"}:
            return self._resolved_provider(row=user, paid_by="user", owner_user_id=user_id, default_model=default_model, entity_id=entity_id, user_id=user_id)

        return self._resolved_provider(row=system, paid_by="system", owner_user_id=None, default_model=default_model, entity_id=None, user_id=None) if usable(system) else None

    def api_key_for_scope(
        self,
        *,
        scope: str,
        provider: str = "openai",
        entity_id: int | None = None,
        user_id: int | None = None,
    ) -> str:
        row = self._secret_row(scope, provider=provider, entity_id=entity_id, user_id=user_id)
        if not row or not row.get("enabled"):
            return ""
        return str(row.get("apiKey") or "")

    def record_ai_assist_event(
        self,
        *,
        entity_id: int | None,
        user_id: int | None,
        provider: str,
        task_type: str,
        model_name: str,
        context_type: str = "",
        context_id: str | None = None,
        round_number: int = 1,
        round_count: int = 1,
        input_tokens: int = 0,
        cached_input_tokens: int = 0,
        output_tokens: int = 0,
        estimated_cost: float = 0.0,
        paid_by: str = "unknown",
        provider_key_owner_user_id: int | None = None,
        success: bool = True,
        error_message: str | None = None,
        decision_reason: str = "",
        latency_ms: int = 0,
    ) -> int | None:
        safe_context_id = self._uuid_or_none(context_id)
        with self.database.connection() as conn:
            row = conn.execute(
                load_query("ai_assist_event_insert.sql"),
                (
                    entity_id,
                    user_id,
                    provider,
                    task_type,
                    model_name,
                    context_type or "",
                    safe_context_id,
                    int(round_number or 1),
                    int(round_count or 1),
                    int(input_tokens or 0),
                    int(cached_input_tokens or 0),
                    int(output_tokens or 0),
                    float(estimated_cost or 0),
                    paid_by,
                    provider_key_owner_user_id,
                    bool(success),
                    str(error_message or "")[:1000] if error_message else None,
                    str(decision_reason or "")[:1000],
                    int(latency_ms or 0),
                ),
            ).fetchone()
        return int(row["id"]) if row else None

    def record_document_ingest_ai_review(
        self,
        *,
        source_path: str,
        provider: str,
        model_name: str,
        paid_by: str,
        review_text: str,
        review_json: dict[str, Any] | None = None,
        estimated_cost: float = 0.0,
    ) -> int | None:
        with self.database.connection() as conn:
            row = conn.execute(
                load_query("document_ingest_ai_review_insert.sql"),
                (
                    source_path,
                    provider,
                    model_name,
                    paid_by,
                    review_text,
                    json.dumps(review_json or {}),
                    float(estimated_cost or 0),
                ),
            ).fetchone()
        return int(row["id"]) if row else None

    def usage_report(
        self,
        *,
        scope: str = "entity",
        entity_id: int | None = None,
        user_id: int | None = None,
        days: int = 31,
        limit: int = 250,
    ) -> dict[str, Any]:
        usage_scope = scope if scope in {"system", "entity", "user"} else "entity"
        with self.database.connection() as conn:
            rows = conn.execute(
                load_query("ai_assist_usage_events.sql"),
                (
                    usage_scope,
                    usage_scope,
                    entity_id,
                    usage_scope,
                    user_id,
                    user_id,
                    max(1, int(days)),
                    max(1, int(limit)),
                ),
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
            "byContext": self._usage_breakdown(events, "contextLabel"),
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
        if isinstance(payload.get("pricingOverrides"), list):
            self.save_pricing_overrides(
                scope="system",
                overrides=payload.get("pricingOverrides") or [],
                provider=provider,
                updated_by=updated_by,
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
        if isinstance(payload.get("pricingOverrides"), list):
            self.save_pricing_overrides(
                scope="entity",
                overrides=payload.get("pricingOverrides") or [],
                provider=provider,
                entity_id=int(entity_id),
                updated_by=updated_by,
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
        if isinstance(payload.get("pricingOverrides"), list):
            self.save_pricing_overrides(
                scope="user",
                overrides=payload.get("pricingOverrides") or [],
                provider=provider,
                user_id=int(user_id),
                updated_by=int(user_id),
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

    def _secret_row(
        self,
        scope: str,
        *,
        provider: str,
        entity_id: int | None = None,
        user_id: int | None = None,
    ) -> dict[str, Any] | None:
        try:
            if scope == "system":
                args = (self.encryption_secret(), provider)
                query = "system_ai_provider_secret_get.sql"
            elif scope == "entity":
                if entity_id is None:
                    return None
                args = (self.encryption_secret(), int(entity_id), provider)
                query = "entity_ai_provider_secret_get.sql"
            elif scope == "user":
                if user_id is None:
                    return None
                args = (self.encryption_secret(), int(user_id), provider)
                query = "user_ai_provider_secret_get.sql"
            else:
                return None
            with self.database.connection() as conn:
                row = conn.execute(load_query(query), args).fetchone()
        except Exception as exc:
            if self.logger:
                self.logger.warning(f"AI provider secret lookup failed for {scope}: {exc}")
            return None
        if not row:
            return None
        return {
            "scope": scope,
            "provider": row["provider_code"],
            "enabled": bool(row["enabled"]),
            "apiKey": row.get("api_key") or "",
            "keyPreview": row.get("key_preview") or "",
            "keyPolicy": row.get("key_policy") or ("system" if scope == "system" else scope),
            "assistMode": row.get("assist_mode") or "auto",
            "defaultModel": row.get("default_model") or "",
            "monthlyBudget": float(row.get("monthly_budget") or 0),
            "warnPercent": int(row.get("warn_percent") or 80),
            "stopPercent": int(row.get("stop_percent") or 100),
        }

    @staticmethod
    def _resolved_provider(
        *,
        row: dict[str, Any],
        paid_by: str,
        owner_user_id: int | None,
        default_model: str,
        entity_id: int | None,
        user_id: int | None,
    ) -> dict[str, Any]:
        return {
            "provider": row.get("provider") or "openai",
            "apiKey": row.get("apiKey") or "",
            "assistMode": row.get("assistMode") or "auto",
            "modelName": row.get("defaultModel") or default_model,
            "paidBy": paid_by,
            "providerKeyOwnerUserId": owner_user_id if paid_by == "user" else None,
            "pricingScope": paid_by,
            "pricingEntityId": entity_id if paid_by == "entity" else None,
            "pricingUserId": user_id if paid_by == "user" else None,
            "monthlyBudget": float(row.get("monthlyBudget") or 0),
            "warnPercent": int(row.get("warnPercent") or 80),
            "stopPercent": int(row.get("stopPercent") or 100),
            "scope": row.get("scope"),
        }

    @staticmethod
    def _uuid_or_none(value: str | None) -> str | None:
        if not value:
            return None
        try:
            return str(UUID(str(value)))
        except Exception:
            return None

    def _settings_row(self, row: dict[str, Any] | None, *, scope: str, provider: str) -> dict[str, Any]:
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
            "pricingOverrides": [],
        }
        scope_entity_id = int(row.get("entity_id")) if row.get("entity_id") is not None else None
        scope_user_id = int(row.get("user_id")) if row.get("user_id") is not None else None
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
            "pricingOverrides": self.pricing_overrides(
                scope=scope,
                provider=provider,
                entity_id=scope_entity_id,
                user_id=scope_user_id,
            ),
        }

    def _usage_event_row(self, row: dict[str, Any]) -> dict[str, Any]:
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
            "contextLabel": self._context_label(row.get("context_type"), row.get("context_id")),
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
            "decisionReason": row.get("decision_reason") or "",
            "latencyMs": int(row.get("latency_ms") or 0),
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

    @staticmethod
    def _context_label(context_type: Any, context_id: Any) -> str:
        if not context_type:
            return "Unscoped"
        if not context_id:
            return str(context_type)
        return f"{context_type}:{str(context_id)[:8]}"
