from __future__ import annotations

from typing import Any

from backend.services.resource_sensors import read_gpu_status


def recommended_embedding_batch(config: Any, gpu_status: dict[str, Any]):
    total_mib = gpu_status.get("memoryTotalMiB") if gpu_status.get("available") else None
    if not total_mib:
        return max(16, int(config.get("EMBED_BATCH_SIZE", 16)))
    total_gib = float(total_mib) / 1024.0
    return max(16, min(256, int(total_gib * 6.5)))


def recommended_rerank_batch(config: Any, gpu_status: dict[str, Any]):
    total_mib = gpu_status.get("memoryTotalMiB") if gpu_status.get("available") else None
    if not total_mib:
        return int(config.get("RERANK_BATCH_SIZE", 32))
    total_gib = float(total_mib) / 1024.0
    return max(16, min(128, int(total_gib * 4)))


def effective_embedding_batch_size(config: Any, gpu_status: dict[str, Any] | None = None):
    configured = int(config.get("EMBED_BATCH_SIZE", 16))
    if str(config.get("EMBED_BATCH_AUTO", True)).lower() in {"0", "false", "no", "off"}:
        return configured
    return max(configured, recommended_embedding_batch(config, gpu_status or read_gpu_status()))


def effective_rerank_batch_size(config: Any, gpu_status: dict[str, Any] | None = None):
    configured = int(config.get("RERANK_BATCH_SIZE", 32))
    if str(config.get("RERANK_BATCH_AUTO", True)).lower() in {"0", "false", "no", "off"}:
        return configured
    return max(configured, recommended_rerank_batch(config, gpu_status or read_gpu_status()))


def build_runtime_batch_status(
    *,
    config: Any,
    embedding_model: str | None,
    reranker_model: str | None,
    gpu_status: dict[str, Any],
    model_device: str | None = None,
):
    embedding_configured = int(config.get("EMBED_BATCH_SIZE", 16))
    rerank_configured = int(config.get("RERANK_BATCH_SIZE", 32))
    embedding_recommended = recommended_embedding_batch(config, gpu_status)
    rerank_recommended = recommended_rerank_batch(config, gpu_status)
    embedding_auto = str(config.get("EMBED_BATCH_AUTO", True)).lower() not in {"0", "false", "no", "off"}
    rerank_auto = str(config.get("RERANK_BATCH_AUTO", True)).lower() not in {"0", "false", "no", "off"}
    return {
        "embedding": {
            "model": embedding_model,
            "device": model_device,
            "configured": embedding_configured,
            "recommended": embedding_recommended,
            "active": effective_embedding_batch_size(config, gpu_status),
            "auto": embedding_auto,
        },
        "reranker": {
            "model": reranker_model,
            "device": model_device,
            "configured": rerank_configured,
            "recommended": rerank_recommended,
            "active": effective_rerank_batch_size(config, gpu_status),
            "auto": rerank_auto,
        },
    }
