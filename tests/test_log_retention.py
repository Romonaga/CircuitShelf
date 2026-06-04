import os
import tempfile
import time
import unittest
from pathlib import Path

from backend.services.log_retention import cleanup_old_logs


class LogRetentionTests(unittest.TestCase):
    def test_removes_old_matching_logs_only(self):
        now = time.time()
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir)
            old_timestamped = log_dir / "trace_2026-05-01_10-00-00.log"
            old_rotated = log_dir / "trace.log.2026-05-01"
            new_timestamped = log_dir / "trace_2026-05-22_10-00-00.log"
            unrelated = log_dir / "other_2026-05-01_10-00-00.log"

            for path in [old_timestamped, old_rotated, new_timestamped, unrelated]:
                path.write_text("log", encoding="utf-8")

            old_mtime = now - (10 * 86400)
            new_mtime = now - 3600
            for path in [old_timestamped, old_rotated, unrelated]:
                os.utime(path, (old_mtime, old_mtime))
            os.utime(new_timestamped, (new_mtime, new_mtime))

            result = cleanup_old_logs(log_dir / "trace.log", None, retention_days=7, now=now)

            self.assertEqual(result.removed, 2)
            self.assertFalse(old_timestamped.exists())
            self.assertFalse(old_rotated.exists())
            self.assertTrue(new_timestamped.exists())
            self.assertTrue(unrelated.exists())

    def test_keeps_active_log_even_when_old(self):
        now = time.time()
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir)
            active = log_dir / "trace_2026-05-01_10-00-00.log"
            active.write_text("active", encoding="utf-8")
            old_mtime = now - (10 * 86400)
            os.utime(active, (old_mtime, old_mtime))

            result = cleanup_old_logs(log_dir / "trace.log", active, retention_days=7, now=now)

            self.assertEqual(result.removed, 0)
            self.assertTrue(active.exists())

    def test_zero_retention_disables_cleanup(self):
        now = time.time()
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir)
            old_log = log_dir / "trace_2026-05-01_10-00-00.log"
            old_log.write_text("log", encoding="utf-8")
            old_mtime = now - (10 * 86400)
            os.utime(old_log, (old_mtime, old_mtime))

            result = cleanup_old_logs(log_dir / "trace.log", None, retention_days=0, now=now)

            self.assertEqual(result.removed, 0)
            self.assertEqual(result.checked, 0)
            self.assertTrue(old_log.exists())


if __name__ == "__main__":
    unittest.main()
