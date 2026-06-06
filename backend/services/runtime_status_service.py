from __future__ import annotations

import threading
from typing import Any

from backend.services.resource_monitor import (
    build_resource_peaks,
    build_resource_status,
    build_runtime_batch_status,
    effective_embedding_batch_size,
    effective_rerank_batch_size,
    read_gpu_status,
    recommended_embedding_batch,
    recommended_rerank_batch,
    reset_resource_peak_window,
)


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
        model_device_name: str | None,
        detected_cpu_count_fn,
        reserved_core_count_fn,
        usable_core_count_fn,
        active_document_worker_count_fn,
        index_status: dict,
        ingest_status_provider=None,
        local_llm_status_provider=None,
        gpu_model_residency_provider=None,
        local_gpu_queue_provider=None,
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
        self.model_device_name = model_device_name
        self.detected_cpu_count_fn = detected_cpu_count_fn
        self.reserved_core_count_fn = reserved_core_count_fn
        self.usable_core_count_fn = usable_core_count_fn
        self.active_document_worker_count_fn = active_document_worker_count_fn
        self.index_status = index_status
        self.ingest_status_provider = ingest_status_provider
        self.local_llm_status_provider = local_llm_status_provider
        self.gpu_model_residency_provider = gpu_model_residency_provider
        self.local_gpu_queue_provider = local_gpu_queue_provider
        self._sampler_stop = threading.Event()
        self._sampler_thread: threading.Thread | None = None

    def build_runtime_status(self) -> dict[str, Any]:
        vector_counts = self.vector_store.counts()
        image_counts = self.image_store.counts()
        image_ids = self.state.get_image_id_list()
        cpu_count = self.detected_cpu_count_fn()
        system_resources = build_resource_status(cpu_count)
        ingest_status = self._current_ingest_status()
        active_document_workers = self._active_document_workers_from_status(ingest_status)
        document_worker_capacity = self._document_worker_capacity_from_status(ingest_status, active_document_workers)
        system_resources["peaks"] = build_resource_peaks(system_resources, active_document_workers)
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
            "databasePool": self.database.pool_stats() if hasattr(self.database, "pool_stats") else {"enabled": False},
            "ingestWorkerBudget": {
                "cpuCores": cpu_count,
                "reservedCores": self.reserved_core_count_fn(cpu_count),
                "usableCores": self.usable_core_count_fn(cpu_count),
                "activeDocumentWorkers": active_document_workers,
                "documentWorkerCapacity": document_worker_capacity,
            },
            "runtimeBatches": build_runtime_batch_status(
                config=self.config,
                embedding_model=self.embedding_model_name,
                reranker_model=self.reranker_model_name,
                model_device=self.model_device_name,
                gpu_status=system_resources.get("gpu", {}),
            ),
            "gpuModels": self._gpu_model_residency(),
            "localGpuQueue": self._local_gpu_queue_status(),
            "localLlmQueue": self._local_llm_status(),
            "systemResources": system_resources,
            "ingest": ingest_status,
        }
        self.performance_store.record_resource_sample(payload)
        return payload

    def _current_ingest_status(self) -> dict[str, Any]:
        if self.ingest_status_provider:
            try:
                status = self.ingest_status_provider()
                if status:
                    return dict(status)
            except Exception:
                pass
        return dict(self.index_status)

    def _local_llm_status(self) -> dict[str, Any]:
        if not self.local_llm_status_provider:
            return {"enabled": False}
        try:
            status = dict(self.local_llm_status_provider() or {})
            status["enabled"] = True
            return status
        except Exception:
            return {"enabled": False, "error": "unavailable"}

    def _gpu_model_residency(self) -> dict[str, Any]:
        if not self.gpu_model_residency_provider:
            return {"available": False}
        try:
            status = dict(self.gpu_model_residency_provider() or {})
            status["available"] = True
            return status
        except Exception:
            return {"available": False, "error": "unavailable"}

    def _local_gpu_queue_status(self) -> dict[str, Any]:
        if not self.local_gpu_queue_provider:
            return {"enabled": False}
        try:
            return dict(self.local_gpu_queue_provider() or {"enabled": False})
        except Exception:
            return {"enabled": False, "error": "unavailable"}

    def _active_document_workers_from_status(self, ingest_status: dict[str, Any]) -> int:
        if not ingest_status.get("running"):
            return 0
        try:
            local_count = int(self.active_document_worker_count_fn() or 0)
        except Exception:
            local_count = 0
        if local_count:
            return local_count
        details = ingest_status.get("details") or {}
        if details.get("activeDocumentWorkers") is not None:
            try:
                return int(details.get("activeDocumentWorkers") or 0)
            except (TypeError, ValueError):
                pass
        if details.get("activeWorkers") is not None:
            try:
                return int(details.get("activeWorkers") or 0)
            except (TypeError, ValueError):
                pass
        return 0

    def _document_worker_capacity_from_status(self, ingest_status: dict[str, Any], active_document_workers: int) -> int:
        if not ingest_status.get("running"):
            return 0
        details = ingest_status.get("details") or {}
        for key in ("activeWorkers", "documentWorkerCapacity", "configuredDocumentWorkers"):
            if details.get(key) is not None:
                try:
                    value = int(details.get(key) or 0)
                    if value > 0:
                        return value
                except (TypeError, ValueError):
                    pass
        if active_document_workers > 0:
            return active_document_workers
        return 0

    def start_resource_sampler(self):
        if self._sampler_thread and self._sampler_thread.is_alive():
            return
        interval = max(1, int(getattr(self.performance_store, "sample_interval_seconds", 5)))
        self._sampler_stop.clear()

        def loop():
            while not self._sampler_stop.wait(interval):
                try:
                    self.build_runtime_status()
                except Exception:
                    # Sampling must never destabilize ingestion or request handling.
                    continue

        self._sampler_thread = threading.Thread(target=loop, name="circuitshelf-resource-sampler", daemon=True)
        self._sampler_thread.start()

    def stop_resource_sampler(self):
        self._sampler_stop.set()
        if self._sampler_thread and self._sampler_thread.is_alive():
            self._sampler_thread.join(timeout=2)
        self._sampler_thread = None

    def build_readiness_status(self) -> tuple[bool, dict[str, Any]]:
        runtime = self.build_runtime_status()
        checks = {
            "modelConfigured": bool(self.llm_model_name),
            "embeddingModelConfigured": bool(self.embedding_model_name),
            "databaseConfigured": self.database.configured,
            "databaseReachable": self.database.health_check(),
        }
        retrieval = {
            "indexedDocumentsAvailable": runtime["sources"] > 0,
            "textChunksLoaded": runtime["chunks"] > 0,
            "textIndexLoaded": runtime["vectorEmbeddings"] > 0,
            "embeddingsLoaded": runtime["embeddings"] > 0,
            "pendingReview": runtime["pendingReview"],
            "state": "ready"
            if runtime["chunks"] > 0 and runtime["vectorEmbeddings"] > 0
            else "pending_review"
            if runtime["pendingReview"] > 0
            else "empty",
        }
        ready = all(checks.values())
        return ready, {
            "status": "ready" if ready else "not_ready",
            "service": "CircuitShelf",
            "checks": checks,
            "retrieval": retrieval,
            "runtime": runtime,
        }
