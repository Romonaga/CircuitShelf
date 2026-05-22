import unittest

from ingest_workers import document_worker_count, ocr_worker_count, reserved_core_count, usable_core_count


class IngestWorkerTests(unittest.TestCase):
    def test_reserves_two_cores_on_large_machines(self):
        self.assertEqual(reserved_core_count(32), 2)
        self.assertEqual(usable_core_count(32), 30)

    def test_reserves_less_on_small_machines(self):
        self.assertEqual(reserved_core_count(2), 0)
        self.assertEqual(reserved_core_count(4), 1)

    def test_document_workers_use_half_available_cores(self):
        self.assertEqual(document_worker_count(1, cpu_count=32), 1)
        self.assertEqual(document_worker_count(9, cpu_count=32), 9)
        self.assertEqual(document_worker_count(40, cpu_count=32), 15)

    def test_ocr_workers_share_available_cores_with_active_documents(self):
        self.assertEqual(ocr_worker_count(100, active_document_workers=1, cpu_count=32), 30)
        self.assertEqual(ocr_worker_count(100, active_document_workers=10, cpu_count=32), 3)
        self.assertEqual(ocr_worker_count(2, active_document_workers=10, cpu_count=32), 2)


if __name__ == "__main__":
    unittest.main()
