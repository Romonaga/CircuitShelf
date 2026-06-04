from __future__ import annotations

import threading
from datetime import datetime


RESOURCE_PEAK_LOCK = threading.Lock()
RESOURCE_PEAK_STATE: dict[str, float | int | None] = {
    "cpuPercent": None,
    "cpuTemperatureC": None,
    "cpuPowerW": None,
    "processCpuPercent": None,
    "memoryUsedPercent": None,
    "processMemoryBytes": None,
    "processThreads": None,
    "gpuPercent": None,
    "gpuMemoryUsedPercent": None,
    "gpuMemoryUsedMiB": None,
    "gpuTemperatureC": None,
    "gpuPowerW": None,
    "activeDocumentWorkers": None,
}
RESOURCE_PEAK_WINDOW: dict[str, str | None] = {
    "date": None,
    "startedAt": None,
}


def reset_resource_peak_window(now: datetime | None = None) -> dict[str, str | None]:
    with RESOURCE_PEAK_LOCK:
        local_now = _local_peak_time(now)
        for key in RESOURCE_PEAK_STATE:
            RESOURCE_PEAK_STATE[key] = None
        RESOURCE_PEAK_WINDOW["date"] = local_now.date().isoformat()
        RESOURCE_PEAK_WINDOW["startedAt"] = local_now.isoformat()
        return dict(RESOURCE_PEAK_WINDOW)


def build_resource_peaks(resources: dict, active_document_workers: int, now: datetime | None = None):
    cpu = resources.get("cpu") or {}
    memory = resources.get("memory") or {}
    process = resources.get("process") or {}
    gpu = resources.get("gpu") or {}
    with RESOURCE_PEAK_LOCK:
        window_date, window_started_at = _ensure_daily_peak_window_locked(now)
        return {
            "windowDate": window_date,
            "windowStartedAt": window_started_at,
            "cpuPercent": _max_peak_locked("cpuPercent", cpu.get("utilizationPercent")),
            "cpuTemperatureC": _max_peak_locked("cpuTemperatureC", cpu.get("temperatureC")),
            "cpuPowerW": _max_peak_locked("cpuPowerW", cpu.get("powerW")),
            "processCpuPercent": _max_peak_locked("processCpuPercent", process.get("cpuPercent")),
            "memoryUsedPercent": _max_peak_locked("memoryUsedPercent", memory.get("usedPercent")),
            "processMemoryBytes": _max_peak_locked("processMemoryBytes", process.get("memoryBytes")),
            "processThreads": _max_peak_locked("processThreads", process.get("threads")),
            "gpuPercent": _max_peak_locked("gpuPercent", gpu.get("utilizationPercent") if gpu.get("available") else None),
            "gpuMemoryUsedPercent": _max_peak_locked("gpuMemoryUsedPercent", gpu.get("memoryUsedPercent") if gpu.get("available") else None),
            "gpuMemoryUsedMiB": _max_peak_locked("gpuMemoryUsedMiB", gpu.get("memoryUsedMiB") if gpu.get("available") else None),
            "gpuTemperatureC": _max_peak_locked("gpuTemperatureC", gpu.get("temperatureC") if gpu.get("available") else None),
            "gpuPowerW": _max_peak_locked("gpuPowerW", gpu.get("powerW") if gpu.get("available") else None),
            "activeDocumentWorkers": _max_peak_locked("activeDocumentWorkers", active_document_workers),
        }


def _local_peak_time(now: datetime | None = None) -> datetime:
    value = now or datetime.now().astimezone()
    if value.tzinfo is None:
        return value.astimezone()
    return value.astimezone()


def _ensure_daily_peak_window_locked(now: datetime | None = None) -> tuple[str, str]:
    local_now = _local_peak_time(now)
    date_key = local_now.date().isoformat()
    started_at = local_now.isoformat()
    if RESOURCE_PEAK_WINDOW.get("date") != date_key:
        for key in RESOURCE_PEAK_STATE:
            RESOURCE_PEAK_STATE[key] = None
        RESOURCE_PEAK_WINDOW["date"] = date_key
        RESOURCE_PEAK_WINDOW["startedAt"] = started_at
    elif not RESOURCE_PEAK_WINDOW.get("startedAt"):
        RESOURCE_PEAK_WINDOW["startedAt"] = started_at
    return str(RESOURCE_PEAK_WINDOW["date"]), str(RESOURCE_PEAK_WINDOW["startedAt"])


def _max_peak_locked(key: str, value):
    if value is None:
        return RESOURCE_PEAK_STATE.get(key)
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return RESOURCE_PEAK_STATE.get(key)
    previous = RESOURCE_PEAK_STATE.get(key)
    if previous is None or numeric > float(previous):
        RESOURCE_PEAK_STATE[key] = int(numeric) if isinstance(value, int) else numeric
    return RESOURCE_PEAK_STATE.get(key)
