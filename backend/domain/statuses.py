from __future__ import annotations

from enum import IntEnum


class DocumentStatusId(IntEnum):
    PENDING = 1
    NEEDS_REVIEW = 2
    INDEXED = 3
    FAILED = 4
    REMOVED = 5


DOCUMENT_STATUS_CODES: dict[DocumentStatusId, str] = {
    DocumentStatusId.PENDING: "pending",
    DocumentStatusId.NEEDS_REVIEW: "needs_review",
    DocumentStatusId.INDEXED: "indexed",
    DocumentStatusId.FAILED: "failed",
    DocumentStatusId.REMOVED: "removed",
}


def document_status_code(status_id: DocumentStatusId | int) -> str:
    return DOCUMENT_STATUS_CODES[DocumentStatusId(int(status_id))]


class LocalGpuWorkStatusId(IntEnum):
    QUEUED = 1
    RUNNING = 2
    COMPLETED = 3
    FAILED = 4
    TIMED_OUT = 5
    CANCELLED = 6


LOCAL_GPU_WORK_STATUS_CODES: dict[LocalGpuWorkStatusId, str] = {
    LocalGpuWorkStatusId.QUEUED: "queued",
    LocalGpuWorkStatusId.RUNNING: "running",
    LocalGpuWorkStatusId.COMPLETED: "completed",
    LocalGpuWorkStatusId.FAILED: "failed",
    LocalGpuWorkStatusId.TIMED_OUT: "timed_out",
    LocalGpuWorkStatusId.CANCELLED: "cancelled",
}


def local_gpu_work_status_code(status_id: LocalGpuWorkStatusId | int) -> str:
    return LOCAL_GPU_WORK_STATUS_CODES[LocalGpuWorkStatusId(int(status_id))]


class AssemblyPlanStatusId(IntEnum):
    ACTIVE = 1
    COMPLETED = 2
    ARCHIVED = 3


class PerformanceWorkStatusId(IntEnum):
    COMPLETED = 1
    SKIPPED = 2
    FAILED = 3
    CANCELLED = 4
