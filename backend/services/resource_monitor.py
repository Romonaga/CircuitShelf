"""Resource telemetry facade.

The implementation is split by responsibility:
- sensors: host/process/GPU sampling
- batches: GPU-aware embedding and rerank batch sizing
- peaks: daily high-water marks
"""

from __future__ import annotations

from backend.services.resource_batches import (
    build_runtime_batch_status,
    effective_embedding_batch_size,
    effective_rerank_batch_size,
    recommended_embedding_batch,
    recommended_rerank_batch,
)
from backend.services.resource_peaks import build_resource_peaks, reset_resource_peak_window
from backend.services.resource_sensors import build_resource_status, read_gpu_status

__all__ = [
    "build_resource_peaks",
    "build_resource_status",
    "build_runtime_batch_status",
    "effective_embedding_batch_size",
    "effective_rerank_batch_size",
    "read_gpu_status",
    "recommended_embedding_batch",
    "recommended_rerank_batch",
    "reset_resource_peak_window",
]
