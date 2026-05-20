import os
import tempfile
import unittest

from ingest_manifest import FileRecord, IngestManifest


class IngestManifestTests(unittest.TestCase):
    def test_diff_detects_added_modified_removed_and_unchanged(self):
        manifest = IngestManifest(
            manifest_path="unused.json",
            training_dir="training",
            supported_extensions=[".pdf"],
        )
        previous = {
            "old.pdf": FileRecord("old.pdf", 10, 100),
            "changed.pdf": FileRecord("changed.pdf", 10, 100),
            "same.pdf": FileRecord("same.pdf", 10, 100),
        }
        current = {
            "changed.pdf": FileRecord("changed.pdf", 11, 100),
            "new.pdf": FileRecord("new.pdf", 10, 100),
            "same.pdf": FileRecord("same.pdf", 10, 100),
        }

        changes = manifest.diff(previous, current)

        self.assertEqual(changes.added, ["new.pdf"])
        self.assertEqual(changes.modified, ["changed.pdf"])
        self.assertEqual(changes.removed, ["old.pdf"])
        self.assertEqual(changes.unchanged, ["same.pdf"])
        self.assertTrue(changes.has_changes)

    def test_scan_filters_supported_nonempty_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "book.pdf"), "wb") as f:
                f.write(b"pdf")
            with open(os.path.join(tmp, "notes.tmp"), "wb") as f:
                f.write(b"tmp")
            open(os.path.join(tmp, "empty.pdf"), "wb").close()

            manifest = IngestManifest(
                manifest_path=os.path.join(tmp, "manifest.json"),
                training_dir=tmp,
                supported_extensions=[".pdf"],
            )

            self.assertEqual(list(manifest.scan()), ["book.pdf"])


if __name__ == "__main__":
    unittest.main()
