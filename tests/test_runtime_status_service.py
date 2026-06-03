from datetime import datetime, timezone

from backend.services.runtime_status_service import build_resource_peaks, reset_resource_peak_window


def _resources(cpu=0, process_cpu=0, ram=0, gpu=0, vram=0):
    return {
        "cpu": {
            "utilizationPercent": cpu,
            "temperatureC": 50,
            "powerW": 70,
        },
        "memory": {
            "usedPercent": ram,
        },
        "process": {
            "cpuPercent": process_cpu,
            "memoryBytes": 1024,
            "threads": 8,
        },
        "gpu": {
            "available": True,
            "utilizationPercent": gpu,
            "memoryUsedPercent": vram,
            "memoryUsedMiB": 2048,
            "temperatureC": 55,
            "powerW": 120,
        },
    }


def test_resource_peaks_accumulate_within_same_local_day():
    reset_resource_peak_window(datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc))

    first = build_resource_peaks(
        _resources(cpu=40, process_cpu=20, ram=10, gpu=60, vram=25),
        active_document_workers=4,
        now=datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc),
    )
    second = build_resource_peaks(
        _resources(cpu=10, process_cpu=5, ram=8, gpu=20, vram=12),
        active_document_workers=1,
        now=datetime(2026, 6, 1, 18, 0, tzinfo=timezone.utc),
    )

    assert second["windowDate"] == first["windowDate"]
    assert second["cpuPercent"] == 40
    assert second["processCpuPercent"] == 20
    assert second["gpuPercent"] == 60
    assert second["activeDocumentWorkers"] == 4


def test_resource_peaks_reset_on_new_local_day():
    reset_resource_peak_window(datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc))

    build_resource_peaks(
        _resources(cpu=90, process_cpu=70, ram=30, gpu=95, vram=80),
        active_document_workers=12,
        now=datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc),
    )
    next_day = build_resource_peaks(
        _resources(cpu=15, process_cpu=7, ram=12, gpu=25, vram=20),
        active_document_workers=2,
        now=datetime(2026, 6, 2, 12, 0, tzinfo=timezone.utc),
    )

    assert next_day["windowDate"] == "2026-06-02"
    assert next_day["cpuPercent"] == 15
    assert next_day["processCpuPercent"] == 7
    assert next_day["gpuPercent"] == 25
    assert next_day["activeDocumentWorkers"] == 2
