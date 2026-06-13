from contextlib import contextmanager

from backend.services import gpu_work_queue
from backend.services.gpu_work_queue import (
    LocalGpuWorkCoordinator,
    clear_gpu_oom_cooldown,
    current_gpu_oom_cooldown,
    is_cuda_out_of_memory,
    record_cuda_oom,
    resolve_adaptive_ocr_slots,
    resolve_cuda_batch_slots,
    resolve_local_llm_slots,
)


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


def setup_function():
    clear_gpu_oom_cooldown()


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


def test_recent_gpu_work_query_prioritizes_live_rows_with_live_timing():
    query = (gpu_work_queue.load_query("local_gpu_work_recent.sql")).lower()

    assert "when status_id = 1 then extract(epoch from (now() - created_at))" in query
    assert "when status_id = 2 and started_at is not null then extract(epoch from (now() - started_at))" in query
    assert "when 2 then 0" in query
    assert "when 1 then 1" in query
    assert "updated_at desc" in query
    assert "created_at desc" in query


def test_adaptive_ocr_slots_use_full_capacity_with_headroom():
    payload = resolve_adaptive_ocr_slots(
        6,
        {"available": True, "gpuPercent": 35, "memoryUsedPercent": 40, "temperatureC": 55},
    )

    assert payload["enabled"] is True
    assert payload["activeSlots"] == 6
    assert payload["targetSlots"] == 6
    assert payload["maxSlots"] == 6
    assert payload["reason"] == "GPU headroom available"


def test_adaptive_ocr_slots_step_down_under_pressure():
    moderate = resolve_adaptive_ocr_slots(
        8,
        {"available": True, "gpuPercent": 84, "memoryUsedPercent": 60, "temperatureC": 58},
    )
    high = resolve_adaptive_ocr_slots(
        8,
        {"available": True, "gpuPercent": 94, "memoryUsedPercent": 66, "temperatureC": 64},
    )

    assert moderate["activeSlots"] == 6
    assert moderate["targetSlots"] == 6
    assert moderate["reason"] == "moderate GPU pressure"
    assert high["activeSlots"] == 4
    assert high["targetSlots"] == 4
    assert high["reason"] == "high GPU pressure"


def test_adaptive_ocr_slots_keep_capacity_with_low_gpu_and_resident_vram():
    payload = resolve_adaptive_ocr_slots(
        8,
        {"available": True, "gpuPercent": 23, "memoryUsedPercent": 77, "temperatureC": 55},
    )

    assert payload["activeSlots"] == 8
    assert payload["targetSlots"] == 8
    assert payload["reason"] == "GPU headroom available"


def test_adaptive_ocr_slots_back_off_before_vram_is_near_full():
    moderate = resolve_adaptive_ocr_slots(
        8,
        {"available": True, "gpuPercent": 23, "memoryUsedPercent": 79, "temperatureC": 55},
    )
    high = resolve_adaptive_ocr_slots(
        8,
        {"available": True, "gpuPercent": 23, "memoryUsedPercent": 85, "temperatureC": 55},
    )
    hard = resolve_adaptive_ocr_slots(
        8,
        {"available": True, "gpuPercent": 23, "memoryUsedPercent": 89, "temperatureC": 55},
    )

    assert moderate["targetSlots"] == 6
    assert moderate["reason"] == "moderate GPU pressure"
    assert high["targetSlots"] == 4
    assert high["reason"] == "high GPU pressure"
    assert hard["targetSlots"] == 2
    assert hard["reason"] == "thermal or VRAM guard"


def test_adaptive_ocr_slots_clamp_on_vram_or_thermal_guard():
    vram = resolve_adaptive_ocr_slots(
        8,
        {"available": True, "gpuPercent": 30, "memoryUsedPercent": 95, "temperatureC": 60},
    )
    thermal = resolve_adaptive_ocr_slots(
        8,
        {"available": True, "gpuPercent": 30, "memoryUsedPercent": 40, "temperatureC": 83},
    )

    assert vram["activeSlots"] == 2
    assert vram["targetSlots"] == 2
    assert vram["reason"] == "thermal or VRAM guard"
    assert thermal["activeSlots"] == 2
    assert thermal["targetSlots"] == 2
    assert thermal["reason"] == "thermal or VRAM guard"


def test_adaptive_ocr_slots_fall_back_to_configured_capacity_without_telemetry():
    payload = resolve_adaptive_ocr_slots(5, {"available": False})

    assert payload["enabled"] is False
    assert payload["activeSlots"] == 5
    assert payload["targetSlots"] == 5
    assert payload["maxSlots"] == 5


def test_cuda_batch_slots_wait_when_vram_guard_is_active():
    payload = resolve_cuda_batch_slots(
        2,
        {"available": True, "gpuPercent": 40, "memoryUsedPercent": 95, "temperatureC": 58},
    )

    assert payload["targetSlots"] == 0
    assert payload["activeSlots"] == 0
    assert payload["reason"] == "thermal or VRAM guard"


def test_cuda_batch_slots_report_running_work_even_when_guarded():
    payload = resolve_cuda_batch_slots(
        2,
        {"available": True, "gpuPercent": 40, "memoryUsedPercent": 95, "temperatureC": 58},
        running_slots=1,
    )

    assert payload["targetSlots"] == 0
    assert payload["activeSlots"] == 1
    assert payload["runningSlots"] == 1


def test_cuda_batch_slots_use_full_capacity_with_memory_headroom():
    payload = resolve_cuda_batch_slots(
        2,
        {"available": True, "gpuPercent": 96, "memoryUsedPercent": 60, "temperatureC": 58},
    )

    assert payload["targetSlots"] == 2
    assert payload["activeSlots"] == 2
    assert payload["reason"] == "GPU memory headroom available"


def test_local_llm_slots_wait_for_background_work_to_drain():
    payload = resolve_local_llm_slots(
        1,
        {
            "available": True,
            "gpuPercent": 55,
            "memoryUsedPercent": 78,
            "memoryUsedMiB": 19000,
            "memoryTotalMiB": 24576,
            "temperatureC": 62,
        },
        background_running_slots=4,
    )

    assert payload["targetSlots"] == 0
    assert payload["activeSlots"] == 0
    assert payload["pressureLevel"] == "background-drain"
    assert payload["requiredFreeMiB"] == 7372.8


def test_local_llm_slots_start_when_background_work_has_headroom():
    payload = resolve_local_llm_slots(
        1,
        {
            "available": True,
            "gpuPercent": 55,
            "memoryUsedPercent": 35,
            "memoryUsedMiB": 8000,
            "memoryTotalMiB": 24576,
            "temperatureC": 62,
        },
        background_running_slots=4,
    )

    assert payload["targetSlots"] == 1
    assert payload["activeSlots"] == 1
    assert payload["reason"] == "local LLM headroom available"


def test_cuda_oom_detection_matches_torch_error_text():
    assert is_cuda_out_of_memory(RuntimeError("CUDA out of memory. Tried to allocate 34 MiB"))
    assert is_cuda_out_of_memory(RuntimeError("external paddleocr exited 1: Out of memory [NV_ERR_NO_MEMORY]"))
    assert not is_cuda_out_of_memory(RuntimeError("some other cuda warning"))


def test_cuda_oom_cooldown_blocks_cuda_batch_and_single_lanes_ocr():
    record_cuda_oom(resource_class="ocr_cuda", error="Out of memory [NV_ERR_NO_MEMORY]", cooldown_seconds=120)
    cooldown = current_gpu_oom_cooldown()
    pressure = {
        "available": True,
        "gpuPercent": 10,
        "memoryUsedPercent": 30,
        "temperatureC": 50,
        "oomCooldown": cooldown,
    }

    ocr = resolve_adaptive_ocr_slots(8, pressure)
    cuda = resolve_cuda_batch_slots(2, pressure)
    llm = resolve_local_llm_slots(1, {**pressure, "memoryUsedMiB": 1000, "memoryTotalMiB": 24576})

    assert cooldown["active"] is True
    assert ocr["targetSlots"] == 1
    assert ocr["pressureLevel"] == "oom-cooldown"
    assert cuda["targetSlots"] == 0
    assert cuda["reason"] == "recent GPU OOM cooldown"
    assert llm["targetSlots"] == 0


def test_adaptive_ocr_slots_do_not_report_below_running_work():
    payload = resolve_adaptive_ocr_slots(
        6,
        {"available": True, "gpuPercent": 94, "memoryUsedPercent": 65, "temperatureC": 60},
        running_slots=5,
    )

    assert payload["targetSlots"] == 3
    assert payload["activeSlots"] == 5
    assert payload["runningSlots"] == 5


def test_coordinator_keeps_ocr_lanes_on_transient_pressure(monkeypatch):
    coordinator = LocalGpuWorkCoordinator(database=FakeDatabase(), ocr_slot_count=8)
    samples = iter(
        [
            {"available": True, "gpuPercent": 30, "memoryUsedPercent": 40, "temperatureC": 55},
            {"available": True, "gpuPercent": 94, "memoryUsedPercent": 40, "temperatureC": 55},
            {"available": True, "gpuPercent": 30, "memoryUsedPercent": 40, "temperatureC": 55},
        ]
    )
    monkeypatch.setattr(coordinator, "_cached_gpu_pressure", lambda: next(samples))

    assert coordinator._adaptive_ocr_slot_count()["targetSlots"] == 8
    pressure = coordinator._adaptive_ocr_slot_count()
    assert pressure["rawTargetSlots"] == 4
    assert pressure["targetSlots"] == 8
    assert pressure["activeSlots"] == 8
    assert pressure["pressureStrikes"] == 1
    assert coordinator._adaptive_ocr_slot_count()["targetSlots"] == 8


def test_coordinator_reduces_ocr_lanes_after_sustained_pressure(monkeypatch):
    coordinator = LocalGpuWorkCoordinator(database=FakeDatabase(), ocr_slot_count=8)
    samples = iter(
        [
            {"available": True, "gpuPercent": 30, "memoryUsedPercent": 40, "temperatureC": 55},
            {"available": True, "gpuPercent": 94, "memoryUsedPercent": 40, "temperatureC": 55},
            {"available": True, "gpuPercent": 94, "memoryUsedPercent": 40, "temperatureC": 55},
            {"available": True, "gpuPercent": 94, "memoryUsedPercent": 40, "temperatureC": 55},
        ]
    )
    monkeypatch.setattr(coordinator, "_cached_gpu_pressure", lambda: next(samples))

    assert coordinator._adaptive_ocr_slot_count()["targetSlots"] == 8
    assert coordinator._adaptive_ocr_slot_count()["targetSlots"] == 8
    assert coordinator._adaptive_ocr_slot_count()["targetSlots"] == 8
    sustained = coordinator._adaptive_ocr_slot_count()
    assert sustained["rawTargetSlots"] == 4
    assert sustained["targetSlots"] == 4
    assert sustained["activeSlots"] == 4


def test_coordinator_reduces_ocr_lanes_immediately_for_hard_guard(monkeypatch):
    coordinator = LocalGpuWorkCoordinator(database=FakeDatabase(), ocr_slot_count=8)
    samples = iter(
        [
            {"available": True, "gpuPercent": 30, "memoryUsedPercent": 40, "temperatureC": 55},
            {"available": True, "gpuPercent": 30, "memoryUsedPercent": 95, "temperatureC": 55},
        ]
    )
    monkeypatch.setattr(coordinator, "_cached_gpu_pressure", lambda: next(samples))

    assert coordinator._adaptive_ocr_slot_count()["targetSlots"] == 8
    guarded = coordinator._adaptive_ocr_slot_count()
    assert guarded["rawTargetSlots"] == 2
    assert guarded["targetSlots"] == 2
    assert guarded["activeSlots"] == 2


def test_coordinator_reduces_ocr_lanes_immediately_for_oom_cooldown(monkeypatch):
    coordinator = LocalGpuWorkCoordinator(database=FakeDatabase(), ocr_slot_count=8)
    cooldown = {
        "active": True,
        "remainingSeconds": 120.0,
        "lastEvent": {"resourceClass": "ocr_cuda"},
    }
    samples = iter(
        [
            {"available": True, "gpuPercent": 30, "memoryUsedPercent": 40, "temperatureC": 55},
            {
                "available": True,
                "gpuPercent": 30,
                "memoryUsedPercent": 40,
                "temperatureC": 55,
                "oomCooldown": cooldown,
            },
        ]
    )
    monkeypatch.setattr(coordinator, "_cached_gpu_pressure", lambda: next(samples))

    assert coordinator._adaptive_ocr_slot_count()["targetSlots"] == 8
    guarded = coordinator._adaptive_ocr_slot_count()
    assert guarded["rawTargetSlots"] == 1
    assert guarded["targetSlots"] == 1
    assert guarded["activeSlots"] == 1
    assert guarded["pressureLevel"] == "oom-cooldown"


def test_coordinator_reports_running_ocr_lanes_even_when_target_is_lower(monkeypatch):
    coordinator = LocalGpuWorkCoordinator(database=FakeDatabase(), ocr_slot_count=8)
    samples = iter(
        [
            {"available": True, "gpuPercent": 30, "memoryUsedPercent": 40, "temperatureC": 55},
            {"available": True, "gpuPercent": 30, "memoryUsedPercent": 95, "temperatureC": 55},
        ]
    )
    monkeypatch.setattr(coordinator, "_cached_gpu_pressure", lambda: next(samples))

    assert coordinator._adaptive_ocr_slot_count()["targetSlots"] == 8
    guarded = coordinator._adaptive_ocr_slot_count(running_slots=6)
    assert guarded["targetSlots"] == 2
    assert guarded["activeSlots"] == 6
    assert guarded["runningSlots"] == 6


def test_coordinator_pauses_ocr_admission_when_local_llm_is_queued(monkeypatch):
    coordinator = LocalGpuWorkCoordinator(database=FakeDatabase(), ocr_slot_count=8, llm_slot_count=1)
    monkeypatch.setattr(
        coordinator,
        "_cached_gpu_pressure",
        lambda: {"available": True, "gpuPercent": 30, "memoryUsedPercent": 40, "temperatureC": 55},
    )

    slots = coordinator._admission_slot_count_for(
        "ocr_cuda",
        live_counts={"local_llm": {"queued": 1}, "ocr_cuda": {"running": 3}},
    )

    assert slots == 0


def test_coordinator_admits_local_llm_only_after_vram_headroom(monkeypatch):
    coordinator = LocalGpuWorkCoordinator(database=FakeDatabase(), ocr_slot_count=8, llm_slot_count=1)
    monkeypatch.setattr(
        coordinator,
        "_cached_gpu_pressure",
        lambda: {
            "available": True,
            "gpuPercent": 50,
            "memoryUsedPercent": 80,
            "memoryUsedMiB": 20000,
            "memoryTotalMiB": 24576,
            "temperatureC": 62,
        },
    )

    blocked = coordinator._admission_slot_count_for(
        "local_llm",
        live_counts={"local_llm": {"queued": 1}, "ocr_cuda": {"running": 3}},
    )
    allowed_without_background = coordinator._admission_slot_count_for(
        "local_llm",
        live_counts={"local_llm": {"queued": 1}, "ocr_cuda": {"running": 0}},
    )

    assert blocked == 0
    assert allowed_without_background == 1
