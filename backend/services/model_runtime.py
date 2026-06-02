from __future__ import annotations

from typing import Any


def resolve_model_device(config: Any) -> str:
    requested = str(config.get("MODEL_DEVICE", "auto") or "auto").strip().lower()
    if requested and requested != "auto":
        return requested
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"
