"""Training-file manifest and change detection."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


MANIFEST_VERSION = 1


@dataclass(frozen=True)
class FileRecord:
    path: str
    size: int
    mtime_ns: int
    sha256: str | None = None


@dataclass(frozen=True)
class FileChanges:
    added: list[str]
    modified: list[str]
    removed: list[str]
    unchanged: list[str]

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.modified or self.removed)

    @property
    def changed_or_removed(self) -> list[str]:
        return self.modified + self.removed

    @property
    def changed_or_added(self) -> list[str]:
        return self.added + self.modified


class IngestManifest:
    def __init__(
        self,
        manifest_path: str,
        training_dir: str,
        supported_extensions: Iterable[str],
        *,
        recursive: bool = True,
        excluded_dirs: Iterable[str] | None = None,
        hash_files: bool = False,
    ):
        self.manifest_path = manifest_path
        self.training_dir = training_dir
        self.supported_extensions = {ext.lower() for ext in supported_extensions}
        self.recursive = recursive
        self.excluded_dirs = set(excluded_dirs or [])
        self.hash_files = hash_files

    def load(self) -> dict[str, FileRecord]:
        if not os.path.exists(self.manifest_path):
            return {}

        with open(self.manifest_path, "r", encoding="utf-8") as f:
            payload = json.load(f)

        records = payload.get("files", {})
        return {
            path: FileRecord(
                path=path,
                size=int(data["size"]),
                mtime_ns=int(data["mtime_ns"]),
                sha256=data.get("sha256"),
            )
            for path, data in records.items()
        }

    def save(self, records: dict[str, FileRecord]) -> None:
        directory = os.path.dirname(self.manifest_path)
        if directory:
            os.makedirs(directory, exist_ok=True)

        payload = {
            "version": MANIFEST_VERSION,
            "training_dir": self.training_dir,
            "hash_files": self.hash_files,
            "files": {path: asdict(record) for path, record in sorted(records.items())},
        }
        tmp_path = f"{self.manifest_path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, sort_keys=True)
        os.replace(tmp_path, self.manifest_path)

    def scan(self) -> dict[str, FileRecord]:
        records: dict[str, FileRecord] = {}
        for rel_path in self.discover_files():
            full_path = os.path.join(self.training_dir, rel_path)
            stat = os.stat(full_path)
            records[rel_path] = FileRecord(
                path=rel_path,
                size=stat.st_size,
                mtime_ns=stat.st_mtime_ns,
                sha256=self._sha256(full_path) if self.hash_files else None,
            )
        return records

    def discover_files(self) -> list[str]:
        if not os.path.exists(self.training_dir):
            return []

        files = []
        if self.recursive:
            for root, dirnames, filenames in os.walk(self.training_dir):
                dirnames[:] = [
                    dirname for dirname in dirnames
                    if dirname not in self.excluded_dirs
                    and os.path.relpath(os.path.join(root, dirname), self.training_dir) not in self.excluded_dirs
                ]
                for filename in filenames:
                    self._append_supported(files, root, filename)
        else:
            for filename in os.listdir(self.training_dir):
                self._append_supported(files, self.training_dir, filename)

        return sorted(files, key=self._sort_key)

    def diff(self, previous: dict[str, FileRecord], current: dict[str, FileRecord]) -> FileChanges:
        previous_paths = set(previous)
        current_paths = set(current)

        added = sorted(current_paths - previous_paths, key=self._sort_key)
        removed = sorted(previous_paths - current_paths, key=self._sort_key)
        common = previous_paths & current_paths
        modified = sorted(
            (
                path for path in common
                if previous[path].size != current[path].size
                or previous[path].mtime_ns != current[path].mtime_ns
                or previous[path].sha256 != current[path].sha256
            ),
            key=self._sort_key,
        )
        unchanged = sorted(common - set(modified), key=self._sort_key)

        return FileChanges(added=added, modified=modified, removed=removed, unchanged=unchanged)

    def _append_supported(self, files: list[str], root: str, filename: str) -> None:
        if filename.startswith("~$"):
            return
        full_path = os.path.join(root, filename)
        if not os.path.isfile(full_path) or os.path.getsize(full_path) <= 0:
            return
        if Path(filename).suffix.lower() not in self.supported_extensions:
            return
        files.append(os.path.relpath(full_path, self.training_dir))

    @staticmethod
    def _sha256(path: str) -> str:
        digest = hashlib.sha256()
        with open(path, "rb") as f:
            for block in iter(lambda: f.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    @staticmethod
    def _sort_key(path: str) -> tuple[int, str]:
        stem = Path(path).stem
        digits = "".join(char for char in stem if char.isdigit())
        return (int(digits) if digits else 0, path.lower())
