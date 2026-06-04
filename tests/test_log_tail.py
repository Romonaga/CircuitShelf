import os
import tempfile
import unittest

from backend.services.log_tail import tail_text_file


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


if __name__ == "__main__":
    unittest.main()
