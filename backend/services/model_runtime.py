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


def release_accelerator_memory(logger=None) -> bool:
    """Release unused CUDA allocations after bursty embedding/rerank work."""
    try:
        import gc

        gc.collect()
        import torch

        if not torch.cuda.is_available():
            return False
        torch.cuda.empty_cache()
        try:
            torch.cuda.ipc_collect()
        except Exception:
            pass
        if logger:
            logger.info("🧹 Released unused CUDA allocator memory.")
        return True
    except Exception as exc:
        if logger:
            logger.warning(f"⚠️ CUDA memory cleanup skipped: {exc}")
        return False
