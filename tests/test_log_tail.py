import os
import tempfile
import unittest

from backend.services.log_tail import tail_recent_trace_logs, tail_text_file


class LogTailTests(unittest.TestCase):
    def test_tails_requested_lines(self):
        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as handle:
            path = handle.name
            handle.write("\n".join(f"line {index}" for index in range(20)))

        try:
            tail = tail_text_file(path, max_lines=5)
        finally:
            os.unlink(path)

        self.assertTrue(tail.exists)
        self.assertEqual(tail.lines, ["line 15", "line 16", "line 17", "line 18", "line 19"])
        self.assertTrue(tail.truncated)

    def test_missing_file_returns_empty_tail(self):
        tail = tail_text_file("/tmp/circuitshelf-missing-log-file", max_lines=5)

        self.assertFalse(tail.exists)
        self.assertEqual(tail.lines, [])
        self.assertIsNone(tail.error)

    def test_recent_trace_logs_merge_web_and_worker_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            worker_path = os.path.join(temp_dir, "trace_2026-06-05_18-36-13.log")
            web_path = os.path.join(temp_dir, "trace_2026-06-06_09-22-39.log")
            with open(worker_path, "w", encoding="utf-8") as handle:
                handle.write("[2026-06-06 09:28:01] Worker ingest started\n")
                handle.write("[2026-06-06 09:28:03] Worker ingest page 2\n")
            with open(web_path, "w", encoding="utf-8") as handle:
                handle.write("[2026-06-06 09:22:39] Web server started\n")
                handle.write("[2026-06-06 09:28:02] Web health check\n")

            tail = tail_recent_trace_logs(web_path, max_lines=4, max_files=4)

        self.assertTrue(tail.exists)
        self.assertIn("(+1 files)", tail.path)
        self.assertEqual(
            tail.lines,
            [
                "[2026-06-06 09:22:39] Web server started",
                "[2026-06-06 09:28:01] Worker ingest started",
                "[2026-06-06 09:28:02] Web health check",
                "[2026-06-06 09:28:03] Worker ingest page 2",
            ],
        )


if __name__ == "__main__":
    unittest.main()
