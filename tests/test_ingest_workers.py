import unittest

from ingest_workers import document_worker_count, ocr_worker_count, persist_worker_count, reserved_core_count, usable_core_count


class IngestWorkerTests(unittest.TestCase):
    def test_reserves_interactive_headroom_on_large_machines(self):
        self.assertEqual(reserved_core_count(32), 2)
        self.assertEqual(usable_core_count(32), 30)
        self.assertEqual(reserved_core_count(64), 4)

    def test_reserves_less_on_small_machines(self):
        self.assertEqual(reserved_core_count(2), 0)
        self.assertEqual(reserved_core_count(4), 1)
        self.assertEqual(reserved_core_count(16), 2)

    def test_document_workers_are_capped_for_ui_responsiveness(self):
        self.assertEqual(document_worker_count(1, cpu_count=32), 1)
        self.assertEqual(document_worker_count(9, cpu_count=32), 9)
        self.assertEqual(document_worker_count(40, cpu_count=32), 15)
        self.assertEqual(document_worker_count(80, cpu_count=64), 16)

    def test_persist_workers_keep_save_queue_parallel_but_bounded(self):
        self.assertEqual(persist_worker_count(0, cpu_count=32), 0)
        self.assertEqual(persist_worker_count(1, cpu_count=32), 1)
        self.assertEqual(persist_worker_count(3, cpu_count=32), 3)
        self.assertEqual(persist_worker_count(80, cpu_count=32), 10)
        self.assertEqual(persist_worker_count(80, cpu_count=64), 10)

    def test_ocr_workers_share_bounded_budget_with_active_documents(self):
        self.assertEqual(ocr_worker_count(100, active_document_workers=1, cpu_count=32), 8)
        self.assertEqual(ocr_worker_count(100, active_document_workers=6, cpu_count=32), 5)
        self.assertEqual(ocr_worker_count(100, active_document_workers=10, cpu_count=32), 3)
        self.assertEqual(ocr_worker_count(100, active_document_workers=15, cpu_count=32), 2)
        self.assertEqual(ocr_worker_count(2, active_document_workers=6, cpu_count=32), 2)


if __name__ == "__main__":
    unittest.main()
