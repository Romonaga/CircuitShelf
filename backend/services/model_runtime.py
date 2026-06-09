from __future__ import annotations

import threading
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
            logger.debug("Released unused CUDA allocator memory.")
        return True
    except Exception as exc:
        if logger:
            logger.warning(f"⚠️ CUDA memory cleanup skipped: {exc}")
        return False


class LazySentenceTransformer:
    """Load the embedding model only while a burst of work needs it."""

    def __init__(self, model_name: str, *, device: str, logger=None):
        self.model_name = model_name
        self.device = device
        self.logger = logger
        self._model = None
        self._model_lock = threading.Lock()

    @property
    def resident(self) -> bool:
        return self._model is not None

    def _ensure_model(self):
        if self._model is None:
            with self._model_lock:
                if self._model is None:
                    from sentence_transformers import SentenceTransformer

                    if self.logger:
                        self.logger.info(f"🧠 Cold-loading embedding model on device: {self.device}")
                    self._model = SentenceTransformer(self.model_name, device=self.device)
        return self._model

    def encode(self, *args, **kwargs):
        return self._ensure_model().encode(*args, **kwargs)

    def unload(self) -> bool:
        with self._model_lock:
            if self._model is None:
                return False
            self._model = None
            if self.logger:
                self.logger.info("🧹 Unloaded idle embedding model from ingest worker.")
            release_accelerator_memory(self.logger)
            return True
