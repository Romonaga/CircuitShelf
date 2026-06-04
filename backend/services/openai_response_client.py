from __future__ import annotations

import base64
from typing import Any

import requests


class OpenAIResponseClient:
    def __init__(self, *, timeout_seconds: int = 90):
        self.timeout_seconds = timeout_seconds

    def create_response(
        self,
        *,
        api_key: str,
        model: str,
        instructions: str,
        input_text: str,
        max_output_tokens: int,
    ) -> dict[str, Any]:
        response = requests.post(
            "https://api.openai.com/v1/responses",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "instructions": instructions,
                "input": input_text,
                "max_output_tokens": max_output_tokens,
                "store": False,
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return response.json()

    def create_multimodal_response(
        self,
        *,
        api_key: str,
        model: str,
        instructions: str,
        input_text: str,
        image_bytes: bytes,
        mime_type: str,
        max_output_tokens: int,
    ) -> dict[str, Any]:
        image_url = f"data:{mime_type};base64,{base64.b64encode(image_bytes).decode('ascii')}"
        response = requests.post(
            "https://api.openai.com/v1/responses",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "instructions": instructions,
                "input": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": input_text},
                            {"type": "input_image", "image_url": image_url},
                        ],
                    }
                ],
                "max_output_tokens": max_output_tokens,
                "store": False,
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return response.json()


def extract_response_text(data: dict[str, Any]) -> str:
    if data.get("output_text"):
        return str(data["output_text"])
    parts: list[str] = []
    for item in data.get("output") or []:
        for content in item.get("content") or []:
            if content.get("type") == "output_text" and content.get("text"):
                parts.append(str(content["text"]))
    return "\n".join(parts).strip()


def extract_usage(data: dict[str, Any]) -> dict[str, int]:
    usage = data.get("usage") or {}
    input_details = usage.get("input_tokens_details") or {}
    return {
        "inputTokens": int(usage.get("input_tokens") or 0),
        "cachedInputTokens": int(input_details.get("cached_tokens") or 0),
        "outputTokens": int(usage.get("output_tokens") or 0),
    }


def safe_error_message(exc: Exception) -> str:
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        try:
            payload = exc.response.json()
            detail = payload.get("error", {}).get("message") or payload.get("error")
            if detail:
                return str(detail)[:1000]
        except Exception:
            pass
        return f"OpenAI HTTP {exc.response.status_code}"
    return str(exc)[:1000]
