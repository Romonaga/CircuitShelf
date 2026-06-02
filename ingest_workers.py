from __future__ import annotations

import os


def detected_cpu_count() -> int:
    return max(1, int(os.cpu_count() or 1))


def reserved_core_count(cpu_count: int | None = None) -> int:
    cpus = max(1, int(cpu_count or detected_cpu_count()))
    if cpus <= 2:
        return 0
    if cpus <= 8:
        return 1
    if cpus <= 16:
        return 2
    return max(4, min(8, cpus // 4))


def usable_core_count(cpu_count: int | None = None) -> int:
    cpus = max(1, int(cpu_count or detected_cpu_count()))
    return max(1, cpus - reserved_core_count(cpus))


def document_worker_count(file_count: int, cpu_count: int | None = None) -> int:
    files = max(0, int(file_count or 0))
    if files <= 0:
        return 0
    if files == 1:
        return 1
    workers = max(1, usable_core_count(cpu_count) // 4)
    return max(1, min(files, workers, 6))


def ocr_worker_count(item_count: int, active_document_workers: int = 1, cpu_count: int | None = None) -> int:
    items = max(0, int(item_count or 0))
    if items <= 0:
        return 0
    active_workers = max(1, int(active_document_workers or 1))
    ocr_budget = max(1, usable_core_count(cpu_count) // 2)
    workers = max(1, ocr_budget // active_workers)
    return max(1, min(items, workers))
