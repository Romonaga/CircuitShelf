import os
import tempfile
import unittest

from backend.services.process_lock import ProcessLockError, acquire_process_lock, pid_file_process, read_pid_file


class ProcessLockTests(unittest.TestCase):
    def test_lock_writes_and_removes_pid_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "circuitshelf.pid")
            with acquire_process_lock(path, name="TestShelf"):
                self.assertEqual(pid_file_process(path), os.getpid())
                self.assertEqual(read_pid_file(path)["name"], "TestShelf")

            self.assertFalse(os.path.exists(path))

    def test_second_lock_fails_while_first_is_held(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "circuitshelf.pid")
            with acquire_process_lock(path):
                with self.assertRaises(ProcessLockError):
                    with acquire_process_lock(path):
                        pass


if __name__ == "__main__":
    unittest.main()
