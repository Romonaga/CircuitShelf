from __future__ import annotations

from typing import Any

import requests


class OpenAIModelService:
    def __init__(self, ai_provider_store: Any, logger: Any = None, *, timeout_seconds: int = 30):
        self.ai_provider_store = ai_provider_store
        self.logger = logger
        self.timeout_seconds = timeout_seconds

    def list_models_for_scope(
        self,
        *,
        scope: str,
        entity_id: int | None = None,
        user_id: int | None = None,
        provider: str = "openai",
    ) -> list[dict[str, Any]]:
        if provider != "openai":
            raise ValueError(f"Unsupported provider: {provider}")

        api_key = self.ai_provider_store.api_key_for_scope(
            scope=scope,
            provider=provider,
            entity_id=entity_id,
            user_id=user_id,
        )
        if not api_key:
            raise ValueError("Save an OpenAI API key before refreshing available models.")

        response = requests.get(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        models = payload.get("data") if isinstance(payload, dict) else []
        if not isinstance(models, list):
            return []

        return sorted(
            (
                {
                    "id": str(item.get("id") or ""),
                    "ownedBy": str(item.get("owned_by") or ""),
                    "created": int(item.get("created") or 0),
                }
                for item in models
                if isinstance(item, dict) and item.get("id")
            ),
            key=lambda item: item["id"],
        )
