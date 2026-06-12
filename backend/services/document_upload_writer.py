from __future__ import annotations

import os
import shutil
import subprocess
import tarfile
import tempfile
import uuid
import zipfile
from pathlib import PurePosixPath

from fastapi import UploadFile

from backend.ingestion.code_samples import (
    is_ignored_code_bundle_dependency_path,
    is_ignored_upload_path,
    safe_relative_upload_path,
)


ARCHIVE_UPLOAD_EXTENSIONS = {
    ".zip",
    ".tar",
    ".tgz",
    ".tar.gz",
    ".tar.bz2",
    ".tbz2",
    ".tar.xz",
    ".txz",
    ".7z",
}
ARCHIVE_SAFE_EXTENSIONS = {".zip", ".tar", ".tgz", ".gz", ".bz2", ".xz", ".7z"}
ARCHIVE_TIMEOUT_SECONDS = 120
SHEBANG_READ_BYTES = 256


def safe_upload_filename(filename: str, supported_extensions: set[str]) -> str:
    return safe_relative_upload_path(filename, supported_extensions)


def upload_display_name(filename: str | None) -> str:
    return str(filename or "").strip() or "(unnamed file)"


async def write_uploaded_documents(
    files: list[UploadFile],
    overwrite: bool,
    training_dir: str,
    supported_extensions: set[str],
) -> dict:
    if not files:
        raise ValueError("Upload must include at least one file.")

    os.makedirs(training_dir, exist_ok=True)
    training_root = os.path.abspath(training_dir)
    seen_names = set()
    tmp_paths = []
    uploaded = []
    skipped = []

    def skip(filename: str, reason: str) -> None:
        skipped.append({"filename": filename, "reason": reason})

    def prepare_destination(filename: str, display_name: str):
        if is_ignored_upload_path(filename):
            skip(display_name, "ignored project/internal file")
            return None
        try:
            safe_filename = safe_upload_filename(filename, supported_extensions)
        except ValueError as exc:
            skip(display_name, str(exc))
            return None

        if safe_filename in seen_names:
            skip(display_name, f"duplicate file path: {safe_filename}")
            return None
        seen_names.add(safe_filename)

        destination = os.path.abspath(os.path.join(training_dir, safe_filename))
        if not destination.startswith(training_root + os.sep):
            raise ValueError("Upload destination is outside the training directory.")
        if os.path.exists(destination) and not overwrite:
            skip(safe_filename, "already exists")
            return None

        os.makedirs(os.path.dirname(destination), exist_ok=True)
        tmp_path = os.path.join(os.path.dirname(destination), f".{os.path.basename(safe_filename)}.{uuid.uuid4().hex}.upload")
        tmp_paths.append(tmp_path)
        return safe_filename, destination, tmp_path

    def record_tmp_file(filename: str, destination: str, tmp_path: str, bytes_written: int) -> None:
        if bytes_written <= 0:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            skip(filename, "empty file")
            return
        uploaded.append({
            "filename": filename,
            "destination": destination,
            "tmpPath": tmp_path,
            "bytes": bytes_written,
        })

    def copy_staged_file(source_path: str, filename: str, display_name: str) -> bool:
        prepared = prepare_destination(filename, display_name)
        if not prepared:
            return False
        safe_filename, destination, tmp_path = prepared
        bytes_written = 0
        with open(source_path, "rb") as in_file, open(tmp_path, "wb") as out_file:
            while True:
                chunk = in_file.read(1024 * 1024)
                if not chunk:
                    break
                bytes_written += len(chunk)
                out_file.write(chunk)
        record_tmp_file(safe_filename, destination, tmp_path, bytes_written)
        return True

    def copy_extracted_file(source_path: str, filename: str, display_name: str) -> None:
        copy_staged_file(source_path, filename, display_name)

    try:
        with tempfile.TemporaryDirectory(prefix="circuitshelf_upload_") as work_dir:
            for file in files:
                display_name = upload_display_name(file.filename)
                if is_archive_upload_path(file.filename or ""):
                    await expand_uploaded_archive(
                        file,
                        display_name=display_name,
                        supported_extensions=supported_extensions,
                        work_dir=work_dir,
                        skip=skip,
                        copy_extracted_file=copy_extracted_file,
                    )
                    continue

                if can_accept_as_shell_script(file.filename or "", supported_extensions):
                    staged_path, bytes_written = await stage_upload_file(file, work_dir)
                    if bytes_written <= 0:
                        skip(display_name, "empty file")
                    elif is_shell_script_file(staged_path):
                        copy_staged_file(staged_path, shell_script_upload_path(file.filename or ""), display_name)
                    else:
                        skip(display_name, unsupported_file_type_message(supported_extensions))
                    continue

                prepared = prepare_destination(file.filename or "", display_name)
                if not prepared:
                    continue
                safe_filename, destination, tmp_path = prepared
                bytes_written = 0
                with open(tmp_path, "wb") as out_file:
                    while True:
                        chunk = await file.read(1024 * 1024)
                        if not chunk:
                            break
                        bytes_written += len(chunk)
                        out_file.write(chunk)
                record_tmp_file(safe_filename, destination, tmp_path, bytes_written)

        for item in uploaded:
            os.replace(item["tmpPath"], item["destination"])
        return {
            "uploaded": [{"filename": item["filename"], "bytes": item["bytes"]} for item in uploaded],
            "skipped": skipped,
        }
    except Exception:
        for tmp_path in tmp_paths:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        raise
    finally:
        for file in files:
            await file.close()


def is_archive_upload_path(filename: str) -> bool:
    lowered = str(filename or "").replace("\\", "/").lower()
    return any(lowered.endswith(ext) for ext in ARCHIVE_UPLOAD_EXTENSIONS)


def archive_parent_path(filename: str) -> str:
    safe_archive = safe_relative_upload_path(str(filename or ""), ARCHIVE_SAFE_EXTENSIONS)
    return str(PurePosixPath(safe_archive).parent if PurePosixPath(safe_archive).parent != PurePosixPath(".") else "")


async def expand_uploaded_archive(
    file: UploadFile,
    *,
    display_name: str,
    supported_extensions: set[str],
    work_dir: str,
    skip,
    copy_extracted_file,
) -> None:
    if is_ignored_upload_path(file.filename or ""):
        skip(display_name, "ignored project/internal file")
        return
    try:
        parent = archive_parent_path(file.filename or "")
    except ValueError as exc:
        skip(display_name, str(exc))
        return

    archive_dir = tempfile.mkdtemp(prefix="archive_", dir=work_dir)
    archive_path = os.path.join(archive_dir, os.path.basename(str(file.filename or "upload.archive")))
    bytes_written = 0
    with open(archive_path, "wb") as out_file:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            bytes_written += len(chunk)
            out_file.write(chunk)
    if bytes_written <= 0:
        skip(display_name, "empty file")
        return

    extracted_root = os.path.join(archive_dir, "contents")
    os.makedirs(extracted_root, exist_ok=True)
    try:
        extracted_files = extract_archive_files(archive_path, extracted_root)
    except ValueError as exc:
        skip(display_name, str(exc))
        return

    accepted = 0
    for rel_path, source_path in extracted_files:
        combined = "/".join(part for part in (parent, rel_path) if part)
        shown_name = f"{display_name}:{rel_path}"
        if is_ignored_upload_path(combined):
            skip(shown_name, "ignored project/internal file")
            continue
        if is_ignored_code_bundle_dependency_path(combined):
            skip(shown_name, "ignored generated/vendor dependency file")
            continue
        destination_name = combined
        try:
            safe_relative_upload_path(destination_name, supported_extensions)
        except ValueError as exc:
            if can_accept_as_shell_script(destination_name, supported_extensions) and is_shell_script_file(source_path):
                destination_name = shell_script_upload_path(destination_name)
            else:
                skip(shown_name, str(exc))
                continue
        try:
            safe_relative_upload_path(destination_name, supported_extensions)
        except ValueError as exc:
            skip(shown_name, str(exc))
            continue
        copy_extracted_file(source_path, destination_name, shown_name)
        accepted += 1
    if accepted <= 0:
        skip(display_name, "archive contained no supported source files")


def extract_archive_files(archive_path: str, extracted_root: str) -> list[tuple[str, str]]:
    lowered = archive_path.lower()
    if lowered.endswith(".zip"):
        return extract_zip_archive(archive_path, extracted_root)
    if lowered.endswith((".tar", ".tgz", ".tar.gz", ".tar.bz2", ".tbz2", ".tar.xz", ".txz")):
        return extract_tar_archive(archive_path, extracted_root)
    if lowered.endswith(".7z"):
        return extract_7z_archive(archive_path, extracted_root)
    raise ValueError("Unsupported archive type.")


def extract_zip_archive(archive_path: str, extracted_root: str) -> list[tuple[str, str]]:
    extracted = []
    with zipfile.ZipFile(archive_path) as archive:
        for item in archive.infolist():
            if item.is_dir():
                continue
            rel_path = normalized_archive_member_path(item.filename)
            if not rel_path:
                continue
            destination = safe_extracted_destination(extracted_root, rel_path)
            os.makedirs(os.path.dirname(destination), exist_ok=True)
            with archive.open(item) as in_file, open(destination, "wb") as out_file:
                shutil.copyfileobj(in_file, out_file)
            extracted.append((rel_path, destination))
    return sorted(extracted, key=lambda item: item[0].lower())


def extract_tar_archive(archive_path: str, extracted_root: str) -> list[tuple[str, str]]:
    extracted = []
    with tarfile.open(archive_path) as archive:
        for item in archive.getmembers():
            if not item.isfile():
                continue
            rel_path = normalized_archive_member_path(item.name)
            if not rel_path:
                continue
            source = archive.extractfile(item)
            if source is None:
                continue
            destination = safe_extracted_destination(extracted_root, rel_path)
            os.makedirs(os.path.dirname(destination), exist_ok=True)
            with source, open(destination, "wb") as out_file:
                shutil.copyfileobj(source, out_file)
            extracted.append((rel_path, destination))
    return extracted


def extract_7z_archive(archive_path: str, extracted_root: str) -> list[tuple[str, str]]:
    seven_zip = shutil.which("7z")
    if not seven_zip:
        raise ValueError("7z archive support requires the 7z command on the server.")
    result = subprocess.run(
        [seven_zip, "x", "-y", "-bd", "-bb0", f"-o{extracted_root}", "--", archive_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=ARCHIVE_TIMEOUT_SECONDS,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip().splitlines()
        message = detail[-1] if detail else "7z extraction failed."
        raise ValueError(message[:200])
    extracted = []
    root_real = os.path.realpath(extracted_root)
    for root, _dirnames, filenames in os.walk(extracted_root):
        for filename in filenames:
            full_path = os.path.join(root, filename)
            if os.path.islink(full_path):
                continue
            real_path = os.path.realpath(full_path)
            if not real_path.startswith(root_real + os.sep):
                continue
            rel_path = os.path.relpath(real_path, extracted_root)
            normalized = normalized_archive_member_path(rel_path)
            if normalized:
                extracted.append((normalized, real_path))
    return extracted


def normalized_archive_member_path(value: str) -> str:
    raw = str(value or "").replace("\\", "/").strip("/")
    parts = []
    for part in raw.split("/"):
        clean = part.strip()
        if not clean or clean in {".", ".."}:
            return ""
        parts.append(clean)
    return "/".join(parts)


def safe_extracted_destination(extracted_root: str, rel_path: str) -> str:
    target = os.path.abspath(os.path.join(extracted_root, rel_path))
    root = os.path.abspath(extracted_root)
    if not target.startswith(root + os.sep):
        raise ValueError("Archive member path is not allowed.")
    return target


async def stage_upload_file(file: UploadFile, work_dir: str) -> tuple[str, int]:
    staged_path = os.path.join(work_dir, f"upload_{uuid.uuid4().hex}")
    bytes_written = 0
    with open(staged_path, "wb") as out_file:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            bytes_written += len(chunk)
            out_file.write(chunk)
    return staged_path, bytes_written


def can_accept_as_shell_script(filename: str, supported_extensions: set[str]) -> bool:
    return ".sh" in supported_extensions and not PurePosixPath(str(filename or "")).suffix


def shell_script_upload_path(filename: str) -> str:
    cleaned = str(filename or "").replace("\\", "/").rstrip("/")
    return f"{cleaned}.sh"


def is_shell_script_file(path: str) -> bool:
    try:
        with open(path, "rb") as handle:
            prefix = handle.read(SHEBANG_READ_BYTES)
    except OSError:
        return False
    if not prefix.startswith(b"#!"):
        return False
    first_line = prefix.splitlines()[0].decode("utf-8", errors="ignore").lower()
    return any(shell in first_line for shell in (" sh", "/sh", "bash", "zsh", "dash", "ash", "env sh", "env bash"))


def unsupported_file_type_message(supported_extensions: set[str]) -> str:
    allowed = ", ".join(sorted(supported_extensions))
    return f"Unsupported file type. Allowed: {allowed}"
