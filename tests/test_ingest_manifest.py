import os
import tempfile
import unittest

from backend.ingestion.manifest import FileRecord, IngestManifest


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

    def test_scan_accepts_code_sample_files_in_folders(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "blink"), exist_ok=True)
            with open(os.path.join(tmp, "blink", "Blink.ino"), "wb") as f:
                f.write(b"void setup() {}")
            with open(os.path.join(tmp, "blink", "main.go"), "wb") as f:
                f.write(b'package main\nimport "machine"')
            with open(os.path.join(tmp, "blink", "lib.rs"), "wb") as f:
                f.write(b"use embedded_hal::digital::OutputPin;")
            with open(os.path.join(tmp, "blink", "App.tsx"), "wb") as f:
                f.write(b"import React from 'react';")
            with open(os.path.join(tmp, "blink", "library.json"), "wb") as f:
                f.write(b'{"frameworks": "arduino"}')
            with open(os.path.join(tmp, "blink", "go.mod"), "wb") as f:
                f.write(b"module blink")
            with open(os.path.join(tmp, "blink", "notes.tmp"), "wb") as f:
                f.write(b"tmp")

            manifest = IngestManifest(
                manifest_path=os.path.join(tmp, "manifest.json"),
                training_dir=tmp,
                supported_extensions=[".go", ".ino", ".json", ".mod", ".rs", ".tsx"],
            )

            self.assertEqual(
                list(manifest.scan()),
                ["blink/App.tsx", "blink/Blink.ino", "blink/go.mod", "blink/lib.rs", "blink/library.json", "blink/main.go"],
            )


if __name__ == "__main__":
    unittest.main()
