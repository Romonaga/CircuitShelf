from __future__ import annotations

import os
import subprocess
import threading
import time
from datetime import datetime, timezone
from typing import Any


RESOURCE_SAMPLE_LOCK = threading.Lock()
RESOURCE_SAMPLE_STATE: dict[str, tuple[float, ...] | None] = {
    "system": None,
    "process": None,
}


def _read_system_cpu_times():
    try:
        with open("/proc/stat", "r", encoding="utf-8") as handle:
            parts = handle.readline().split()
    except OSError:
        return None
    if not parts or parts[0] != "cpu":
        return None
    values = [float(value) for value in parts[1:]]
    idle = values[3] + (values[4] if len(values) > 4 else 0.0)
    total = sum(values)
    return time.time(), total, idle


def _read_process_cpu_times():
    try:
        with open("/proc/self/stat", "r", encoding="utf-8") as handle:
            fields = handle.read().split()
        ticks = os.sysconf(os.sysconf_names["SC_CLK_TCK"])
        cpu_time = (float(fields[13]) + float(fields[14])) / float(ticks)
    except (OSError, KeyError, IndexError, ValueError):
        return None
    return time.time(), cpu_time


def _percent_from_delta(previous, current, *, process=False):
    if not previous or not current:
        return None
    if process:
        elapsed = max(current[0] - previous[0], 0.001)
        return round(((current[1] - previous[1]) / elapsed) * 100.0, 2)
    total_delta = current[1] - previous[1]
    idle_delta = current[2] - previous[2]
    if total_delta <= 0:
        return None
    return round((1.0 - (idle_delta / total_delta)) * 100.0, 2)


def _read_memory_status():
    status = {}
    try:
        with open("/proc/meminfo", "r", encoding="utf-8") as handle:
            for line in handle:
                key, value = line.split(":", 1)
                status[key] = int(value.strip().split()[0]) * 1024
    except (OSError, ValueError, IndexError):
        return {}
    total = status.get("MemTotal")
    available = status.get("MemAvailable")
    if not total or available is None:
        return {}
    used = total - available
    return {
        "totalBytes": total,
        "usedBytes": used,
        "availableBytes": available,
        "usedPercent": round((used / total) * 100.0, 2),
    }


def _read_process_status():
    result = {"pid": os.getpid()}
    try:
        with open("/proc/self/status", "r", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("VmRSS:"):
                    result["memoryBytes"] = int(line.split()[1]) * 1024
                elif line.startswith("Threads:"):
                    result["threads"] = int(line.split()[1])
    except (OSError, ValueError, IndexError):
        pass
    return result


def read_gpu_status():
    query = "name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw"
    try:
        completed = subprocess.run(
            [
                "nvidia-smi",
                f"--query-gpu={query}",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return {"available": False}
    if completed.returncode != 0 or not completed.stdout.strip():
        return {"available": False, "error": completed.stderr.strip()[:180] or "nvidia-smi unavailable"}
    first = completed.stdout.strip().splitlines()[0]
    parts = [part.strip() for part in first.split(",")]
    if len(parts) < 6:
        return {"available": False, "error": "unexpected nvidia-smi output"}
    try:
        memory_used = float(parts[2])
        memory_total = float(parts[3])
        return {
            "available": True,
            "name": parts[0],
            "utilizationPercent": float(parts[1]),
            "memoryUsedMiB": memory_used,
            "memoryTotalMiB": memory_total,
            "memoryUsedPercent": round((memory_used / memory_total) * 100.0, 2) if memory_total else None,
            "temperatureC": float(parts[4]),
            "powerW": float(parts[5]),
        }
    except ValueError:
        return {"available": False, "error": "could not parse nvidia-smi output"}


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


def build_resource_status(cpu_count: int):
    system_sample = _read_system_cpu_times()
    process_sample = _read_process_cpu_times()
    with RESOURCE_SAMPLE_LOCK:
        previous_system = RESOURCE_SAMPLE_STATE.get("system")
        previous_process = RESOURCE_SAMPLE_STATE.get("process")
        if system_sample:
            RESOURCE_SAMPLE_STATE["system"] = system_sample
        if process_sample:
            RESOURCE_SAMPLE_STATE["process"] = process_sample
    process = _read_process_status()
    process["cpuPercent"] = _percent_from_delta(previous_process, process_sample, process=True)
    return {
        "sampledAt": datetime.now(timezone.utc).isoformat(),
        "cpu": {
            "cores": cpu_count,
            "utilizationPercent": _percent_from_delta(previous_system, system_sample),
            "loadAverage": list(os.getloadavg()) if hasattr(os, "getloadavg") else None,
        },
        "memory": _read_memory_status(),
        "process": process,
        "gpu": read_gpu_status(),
    }


def build_runtime_batch_status(
    *,
    config: Any,
    embedding_model: str | None,
    reranker_model: str | None,
    gpu_status: dict[str, Any],
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
            "configured": embedding_configured,
            "recommended": embedding_recommended,
            "active": max(embedding_configured, embedding_recommended) if embedding_auto else embedding_configured,
            "auto": embedding_auto,
        },
        "reranker": {
            "model": reranker_model,
            "configured": rerank_configured,
            "recommended": rerank_recommended,
            "active": max(rerank_configured, rerank_recommended) if rerank_auto else rerank_configured,
            "auto": rerank_auto,
        },
    }


class RuntimeStatusReporter:
    def __init__(
        self,
        *,
        config: Any,
        state,
        vector_store,
        image_store,
        response_cache,
        performance_store,
        database,
        embedding_model_name: str | None,
        reranker_model_name: str | None,
        llm_model_name: str | None,
        detected_cpu_count_fn,
        reserved_core_count_fn,
        usable_core_count_fn,
        active_document_worker_count_fn,
        index_status: dict,
    ):
        self.config = config
        self.state = state
        self.vector_store = vector_store
        self.image_store = image_store
        self.response_cache = response_cache
        self.performance_store = performance_store
        self.database = database
        self.embedding_model_name = embedding_model_name
        self.reranker_model_name = reranker_model_name
        self.llm_model_name = llm_model_name
        self.detected_cpu_count_fn = detected_cpu_count_fn
        self.reserved_core_count_fn = reserved_core_count_fn
        self.usable_core_count_fn = usable_core_count_fn
        self.active_document_worker_count_fn = active_document_worker_count_fn
        self.index_status = index_status

    def build_runtime_status(self) -> dict[str, Any]:
        vector_counts = self.vector_store.counts()
        image_counts = self.image_store.counts()
        image_ids = self.state.get_image_id_list()
        cpu_count = self.detected_cpu_count_fn()
        system_resources = build_resource_status(cpu_count)
        payload = {
            "chunks": vector_counts.get("chunks", 0),
            "sources": vector_counts.get("documents", 0),
            "embeddings": vector_counts.get("embeddings", 0),
            "vectorChunks": vector_counts.get("chunks", 0),
            "vectorEmbeddings": vector_counts.get("embeddings", 0),
            "imageIds": len(image_ids),
            "imageEmbeddings": image_counts.get("embeddings", 0),
            "pendingReview": self.vector_store.pending_review_count(),
            "cacheStats": self.response_cache.stats(),
            "ingestWorkerBudget": {
                "cpuCores": cpu_count,
                "reservedCores": self.reserved_core_count_fn(cpu_count),
                "usableCores": self.usable_core_count_fn(cpu_count),
                "activeDocumentWorkers": self.active_document_worker_count_fn() if self.index_status.get("running") else 0,
            },
            "runtimeBatches": build_runtime_batch_status(
                config=self.config,
                embedding_model=self.embedding_model_name,
                reranker_model=self.reranker_model_name,
                gpu_status=system_resources.get("gpu", {}),
            ),
            "systemResources": system_resources,
            "ingest": dict(self.index_status),
        }
        self.performance_store.record_resource_sample(payload)
        return payload

    def build_readiness_status(self) -> tuple[bool, dict[str, Any]]:
        runtime = self.build_runtime_status()
        checks = {
            "modelConfigured": bool(self.llm_model_name),
            "embeddingModelConfigured": bool(self.embedding_model_name),
            "textChunksLoaded": runtime["chunks"] > 0,
            "textIndexLoaded": runtime["vectorEmbeddings"] > 0,
            "embeddingsLoaded": runtime["embeddings"] > 0,
            "databaseConfigured": self.database.configured,
            "databaseReachable": self.database.health_check(),
        }
        ready = all(checks.values())
        return ready, {
            "status": "ready" if ready else "not_ready",
            "service": "CircuitShelf",
            "checks": checks,
            "runtime": runtime,
        }
