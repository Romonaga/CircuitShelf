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


def read_text_file(path: str) -> str | None:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read().strip()
    except (OSError, TypeError, UnicodeDecodeError):
        return None


def read_millidegree_file(path: str) -> float | None:
    value = read_text_file(path)
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


def read_microwatt_file(path: str) -> float | None:
    value = read_text_file(path)
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


def read_cpu_temperature_status() -> dict[str, Any]:
    return _read_cpu_temperature_status()


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
        sensor_name = (read_text_file(os.path.join(path, "name")) or "").strip()
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
            label = read_text_file(os.path.join(path, f"{prefix}_label")) or sensor_name
            temperature = read_millidegree_file(os.path.join(path, filename))
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
        zone_type = read_text_file(os.path.join(path, "type")) or zone
        temperature = read_millidegree_file(os.path.join(path, "temp"))
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
        sensor_name = (read_text_file(os.path.join(path, "name")) or "").strip()
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
            label = read_text_file(os.path.join(path, f"{prefix}_label")) or sensor_name
            power_w = read_microwatt_file(os.path.join(path, filename))
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
