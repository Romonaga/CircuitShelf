from __future__ import annotations

import os
from typing import Any


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
    return max(2, min(4, cpus // 16))


def usable_core_count(cpu_count: int | None = None) -> int:
    cpus = max(1, int(cpu_count or detected_cpu_count()))
    return max(1, cpus - reserved_core_count(cpus))


def cpu_thermal_worker_pressure(
    configured_workers: int,
    cpu_temperature_c: float | None = None,
) -> dict[str, Any]:
    workers = max(0, int(configured_workers or 0))
    if workers <= 1:
        return {
            "enabled": False,
            "temperatureC": cpu_temperature_c,
            "level": "not_applicable",
            "targetWorkers": workers,
            "reason": "single-worker workload",
        }
    try:
        temperature = None if cpu_temperature_c is None else float(cpu_temperature_c)
    except (TypeError, ValueError):
        temperature = None
    if temperature is None:
        return {
            "enabled": False,
            "temperatureC": None,
            "level": "unavailable",
            "targetWorkers": workers,
            "reason": "cpu temperature unavailable",
        }

    if temperature >= 95.0:
        ratio = 1 / workers
        level = "hard"
        reason = "CPU thermal guard at Tjmax"
    elif temperature >= 92.0:
        ratio = 0.50
        level = "high"
        reason = "high CPU temperature"
    elif temperature >= 90.0:
        ratio = 0.75
        level = "moderate"
        reason = "moderate CPU temperature"
    else:
        ratio = 1.0
        level = "headroom"
        reason = "CPU thermal headroom available"

    target = max(1, min(workers, int(round(workers * ratio))))
    return {
        "enabled": True,
        "temperatureC": round(temperature, 2),
        "level": level,
        "targetWorkers": target,
        "configuredWorkers": workers,
        "reason": reason,
    }


def document_worker_count(
    file_count: int,
    cpu_count: int | None = None,
    *,
    cpu_temperature_c: float | None = None,
) -> int:
    files = max(0, int(file_count or 0))
    if files <= 0:
        return 0
    if files == 1:
        return 1
    workers = max(1, usable_core_count(cpu_count) // 2)
    configured = max(1, min(files, workers, 16))
    return int(cpu_thermal_worker_pressure(configured, cpu_temperature_c)["targetWorkers"])


def persist_worker_count(file_count: int, cpu_count: int | None = None) -> int:
    files = max(0, int(file_count or 0))
    if files <= 0:
        return 0
    if files == 1:
        return 1
    usable = usable_core_count(cpu_count)
    workers = max(1, usable // 3)
    return max(1, min(files, workers, 10))


def ocr_worker_count(item_count: int, active_document_workers: int = 1, cpu_count: int | None = None) -> int:
    items = max(0, int(item_count or 0))
    if items <= 0:
        return 0
    active_workers = max(1, int(active_document_workers or 1))
    ocr_budget = max(1, usable_core_count(cpu_count))
    workers = max(1, ocr_budget // active_workers)
    return max(1, min(items, workers, 8))
