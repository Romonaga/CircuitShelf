from contextlib import contextmanager

from backend.services import gpu_work_queue
from backend.services.gpu_work_queue import LocalGpuWorkCoordinator


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
