from __future__ import annotations

import os
import re
from typing import Any


def scan_ingest_folder(folder: str, *, config: Any, pdf_ext: str, trace_logger) -> list[str]:
    if not os.path.exists(folder):
        trace_logger.error("Training folder not found.")
        return []

    recursive = config.get("TRAINING_RECURSIVE", True)
    excluded_dirs = set(config.get("TRAINING_EXCLUDE_DIRS", []))
    supported = {pdf_ext, ".docx", ".md", ".txt", ".png", ".jpg", ".jpeg"}

    if recursive:
        return _scan_recursive(folder, supported=supported, excluded_dirs=excluded_dirs)
    return _scan_flat(folder, supported=supported)


def extract_first_number(value: str) -> int:
    match = re.search(r"(\d+)", value)
    return int(match.group(1)) if match else 0


def _scan_recursive(folder: str, *, supported: set[str], excluded_dirs: set[str]) -> list[str]:
    file_list: list[str] = []
    for root, dirnames, filenames in os.walk(folder):
        dirnames[:] = [
            dirname
            for dirname in dirnames
            if dirname not in excluded_dirs
            and os.path.relpath(os.path.join(root, dirname), folder) not in excluded_dirs
        ]
        for filename in filenames:
            fpath = os.path.join(root, filename)
            if _is_supported_file(fpath, filename, supported=supported):
                file_list.append(os.path.relpath(fpath, folder))
    return file_list


def _scan_flat(folder: str, *, supported: set[str]) -> list[str]:
    file_list: list[str] = []
    for filename in os.listdir(folder):
        fpath = os.path.join(folder, filename)
        if _is_supported_file(fpath, filename, supported=supported):
            file_list.append(filename)
    return file_list


def _is_supported_file(fpath: str, filename: str, *, supported: set[str]) -> bool:
    return (
        not filename.startswith("~$")
        and os.path.isfile(fpath)
        and os.path.getsize(fpath) > 0
        and os.path.splitext(filename)[1].lower() in supported
    )
