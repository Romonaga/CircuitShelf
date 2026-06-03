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

CPU_HWMON_NAMES = {
    "coretemp",
    "k10temp",
    "zenpower",
    "cpu_thermal",
    "x86_pkg_temp",
    "fam15h_power",
}
NON_CPU_HWMON_NAMES = {
    "amdgpu",
    "asus",
    "drivetemp",
    "iwlwifi_1",
    "nvme",
    "nvidia",
    "spd5118",
}


def _read_text_file(path: str) -> str | None:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read().strip()
    except OSError:
        return None


def _read_millidegree_file(path: str) -> float | None:
    value = _read_text_file(path)
    if value is None:
        return None
    try:
        number = float(value)
    except ValueError:
        return None
    if number > 1000:
        number = number / 1000.0
    if number < -20 or number > 130:
        return None
    return round(number, 2)


def _read_microwatt_file(path: str) -> float | None:
    value = _read_text_file(path)
    if value is None:
        return None
    try:
        number = float(value)
    except ValueError:
        return None
    if number > 1000:
        number = number / 1_000_000.0
    if number < 0 or number > 2000:
        return None
    return round(number, 2)


def _cpu_temp_score(sensor_name: str, label: str) -> int:
    name = sensor_name.lower()
    normalized_label = label.lower()
    if name in NON_CPU_HWMON_NAMES:
        return -100
    score = 0
    if name in CPU_HWMON_NAMES:
        score += 100
    if "tdie" in normalized_label or "package id 0" in normalized_label:
        score += 30
    elif "tctl" in normalized_label:
        score += 25
    elif "cpu" in normalized_label:
        score += 20
    elif normalized_label.startswith("core"):
        score += 10
    return score


def _cpu_power_score(sensor_name: str, label: str) -> int:
    name = sensor_name.lower()
    normalized_label = label.lower()
    if name in NON_CPU_HWMON_NAMES:
        return -100
    score = 0
    if name in CPU_HWMON_NAMES:
        score += 100
    if "package" in normalized_label or "rapl_p_package" in normalized_label:
        score += 30
    elif "cpu" in normalized_label:
        score += 20
    return score


def _read_cpu_temperature_status() -> dict[str, Any]:
    candidates = []
    hwmon_root = "/sys/class/hwmon"
    try:
        hwmon_dirs = sorted(os.listdir(hwmon_root))
    except OSError:
        hwmon_dirs = []

    for dirname in hwmon_dirs:
        path = os.path.join(hwmon_root, dirname)
        sensor_name = (_read_text_file(os.path.join(path, "name")) or "").strip()
        if not sensor_name:
            continue
        try:
            files = os.listdir(path)
        except OSError:
            continue
        for filename in files:
            if not filename.startswith("temp") or not filename.endswith("_input"):
                continue
            prefix = filename.removesuffix("_input")
            label = _read_text_file(os.path.join(path, f"{prefix}_label")) or sensor_name
            temperature = _read_millidegree_file(os.path.join(path, filename))
            if temperature is None:
                continue
            score = _cpu_temp_score(sensor_name, label)
            if score <= 0:
                continue
            candidates.append((score, temperature, sensor_name, label))

    if candidates:
        score, temperature, sensor_name, label = sorted(candidates, key=lambda item: (item[0], item[1]), reverse=True)[0]
        return {
            "temperatureC": temperature,
            "temperatureSensor": f"{sensor_name}:{label}",
        }

    thermal_root = "/sys/class/thermal"
    try:
        zones = sorted(os.listdir(thermal_root))
    except OSError:
        zones = []
    for zone in zones:
        if not zone.startswith("thermal_zone"):
            continue
        path = os.path.join(thermal_root, zone)
        zone_type = _read_text_file(os.path.join(path, "type")) or zone
        temperature = _read_millidegree_file(os.path.join(path, "temp"))
        if temperature is None:
            continue
        if any(term in zone_type.lower() for term in ("cpu", "x86_pkg_temp", "soc", "package")):
            return {
                "temperatureC": temperature,
                "temperatureSensor": zone_type,
            }
    return {}


def _read_cpu_power_status() -> dict[str, Any]:
    candidates = []
    hwmon_root = "/sys/class/hwmon"
    try:
        hwmon_dirs = sorted(os.listdir(hwmon_root))
    except OSError:
        hwmon_dirs = []

    for dirname in hwmon_dirs:
        path = os.path.join(hwmon_root, dirname)
        sensor_name = (_read_text_file(os.path.join(path, "name")) or "").strip()
        if not sensor_name:
            continue
        try:
            files = os.listdir(path)
        except OSError:
            continue
        for filename in files:
            if not filename.startswith("power") or not filename.endswith("_input"):
                continue
            prefix = filename.removesuffix("_input")
            label = _read_text_file(os.path.join(path, f"{prefix}_label")) or sensor_name
            power_w = _read_microwatt_file(os.path.join(path, filename))
            if power_w is None:
                continue
            score = _cpu_power_score(sensor_name, label)
            if score <= 0:
                continue
            candidates.append((score, power_w, sensor_name, label))

    if not candidates:
        return {}
    _, power_w, sensor_name, label = sorted(candidates, key=lambda item: (item[0], item[1]), reverse=True)[0]
    return {
        "powerW": power_w,
        "powerSensor": f"{sensor_name}:{label}",
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


def reset_resource_peak_window(now: datetime | None = None) -> dict[str, str | None]:
    with RESOURCE_PEAK_LOCK:
        local_now = _local_peak_time(now)
        for key in RESOURCE_PEAK_STATE:
            RESOURCE_PEAK_STATE[key] = None
        RESOURCE_PEAK_WINDOW["date"] = local_now.date().isoformat()
        RESOURCE_PEAK_WINDOW["startedAt"] = local_now.isoformat()
        return dict(RESOURCE_PEAK_WINDOW)


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


def effective_rerank_batch_size(config: Any, gpu_status: dict[str, Any] | None = None):
    configured = int(config.get("RERANK_BATCH_SIZE", 32))
    if str(config.get("RERANK_BATCH_AUTO", True)).lower() in {"0", "false", "no", "off"}:
        return configured
    return max(configured, recommended_rerank_batch(config, gpu_status or read_gpu_status()))


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
            **_read_cpu_temperature_status(),
            **_read_cpu_power_status(),
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


def build_resource_peaks(resources: dict[str, Any], active_document_workers: int, now: datetime | None = None):
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
            },
            "runtimeBatches": build_runtime_batch_status(
                config=self.config,
                embedding_model=self.embedding_model_name,
                reranker_model=self.reranker_model_name,
                model_device=self.model_device_name,
                gpu_status=system_resources.get("gpu", {}),
            ),
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
