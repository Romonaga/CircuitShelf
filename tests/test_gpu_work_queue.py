from contextlib import contextmanager

from backend.services import gpu_work_queue
from backend.services.gpu_work_queue import LocalGpuWorkCoordinator, resolve_adaptive_ocr_slots


class FakeConnection:
    def __init__(self):
        self.executed = []

    def execute(self, query, params=None):
        self.executed.append((query, params))
        return FakeResult([])


class FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows


class FakeDatabase:
    def __init__(self):
        self.conn = FakeConnection()

    @contextmanager
    def connection(self):
        yield self.conn


def test_abandoned_gpu_work_cleanup_runs_periodically(monkeypatch):
    fake_database = FakeDatabase()
    clock = {"now": 100.0}
    monkeypatch.setattr(gpu_work_queue.time, "monotonic", lambda: clock["now"])
    monkeypatch.setattr(gpu_work_queue, "load_query", lambda name: name)
    coordinator = LocalGpuWorkCoordinator(
        database=fake_database,
        cleanup_interval_seconds=30,
        stale_running_after_seconds=300,
        stale_queued_after_seconds=300,
    )

    coordinator.cleanup_abandoned()
    coordinator.cleanup_abandoned()

    assert [query for query, _ in fake_database.conn.executed] == [
        "local_gpu_work_live_process_ids.sql",
        "local_gpu_work_cleanup_abandoned.sql",
    ]

    clock["now"] += 31
    coordinator.cleanup_abandoned()

    assert [query for query, _ in fake_database.conn.executed] == [
        "local_gpu_work_live_process_ids.sql",
        "local_gpu_work_cleanup_abandoned.sql",
        "local_gpu_work_live_process_ids.sql",
        "local_gpu_work_cleanup_abandoned.sql",
    ]


def test_cleanup_abandoned_once_still_only_runs_once(monkeypatch):
    fake_database = FakeDatabase()
    monkeypatch.setattr(gpu_work_queue, "load_query", lambda name: name)
    coordinator = LocalGpuWorkCoordinator(database=fake_database)

    coordinator.cleanup_abandoned_once()
    coordinator.cleanup_abandoned_once()

    assert [query for query, _ in fake_database.conn.executed] == [
        "local_gpu_work_live_process_ids.sql",
        "local_gpu_work_cleanup_abandoned.sql",
    ]


def test_wait_summary_payload_splits_overall_and_resource_rows():
    payload = LocalGpuWorkCoordinator._wait_summary_payload([
        {
            "resource_class": "cuda_batch",
            "queued": 2,
            "running": 1,
            "current_avg_wait_seconds": 1.25,
            "current_max_wait_seconds": 3.5,
            "recent_avg_wait_seconds": 0.5,
            "recent_max_wait_seconds": 2.0,
        },
        {
            "resource_class": "all",
            "queued": 3,
            "running": 2,
            "current_avg_wait_seconds": 2.25,
            "current_max_wait_seconds": 5.0,
            "recent_avg_wait_seconds": 1.5,
            "recent_max_wait_seconds": 4.0,
        },
    ])

    assert payload["overall"]["queued"] == 3
    assert payload["overall"]["currentMaxWaitSeconds"] == 5.0
    assert payload["byResource"]["cuda_batch"]["running"] == 1
    assert payload["byResource"]["cuda_batch"]["recentAvgWaitSeconds"] == 0.5


def test_adaptive_ocr_slots_use_full_capacity_with_headroom():
    payload = resolve_adaptive_ocr_slots(
        6,
        {"available": True, "gpuPercent": 35, "memoryUsedPercent": 40, "temperatureC": 55},
    )

    assert payload["enabled"] is True
    assert payload["activeSlots"] == 6
    assert payload["maxSlots"] == 6
    assert payload["reason"] == "GPU headroom available"


def test_adaptive_ocr_slots_step_down_under_pressure():
    moderate = resolve_adaptive_ocr_slots(
        8,
        {"available": True, "gpuPercent": 76, "memoryUsedPercent": 60, "temperatureC": 58},
    )
    high = resolve_adaptive_ocr_slots(
        8,
        {"available": True, "gpuPercent": 90, "memoryUsedPercent": 66, "temperatureC": 64},
    )

    assert moderate["activeSlots"] == 6
    assert moderate["reason"] == "moderate GPU pressure"
    assert high["activeSlots"] == 4
    assert high["reason"] == "high GPU pressure"


def test_adaptive_ocr_slots_clamp_on_vram_or_thermal_guard():
    vram = resolve_adaptive_ocr_slots(
        8,
        {"available": True, "gpuPercent": 30, "memoryUsedPercent": 93, "temperatureC": 60},
    )
    thermal = resolve_adaptive_ocr_slots(
        8,
        {"available": True, "gpuPercent": 30, "memoryUsedPercent": 40, "temperatureC": 83},
    )

    assert vram["activeSlots"] == 2
    assert vram["reason"] == "thermal or VRAM guard"
    assert thermal["activeSlots"] == 2
    assert thermal["reason"] == "thermal or VRAM guard"


def test_adaptive_ocr_slots_fall_back_to_configured_capacity_without_telemetry():
    payload = resolve_adaptive_ocr_slots(5, {"available": False})

    assert payload["enabled"] is False
    assert payload["activeSlots"] == 5
    assert payload["maxSlots"] == 5
