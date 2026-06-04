from __future__ import annotations

import os
import uuid

from fastapi import UploadFile


def safe_upload_filename(filename: str, supported_extensions: set[str]) -> str:
    name = os.path.basename(str(filename or "")).strip()
    if not name or name in {".", ".."}:
        raise ValueError("Upload must include a file name.")
    if name.startswith(".") or any(char in name for char in ("/", "\\")):
        raise ValueError("Upload file name is not allowed.")
    ext = os.path.splitext(name)[1].lower()
    if ext not in supported_extensions:
        allowed = ", ".join(sorted(supported_extensions))
        raise ValueError(f"Unsupported file type. Allowed: {allowed}")
    return name


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
    prepared = []
    seen_names = set()
    tmp_paths = []
    uploaded = []
    skipped = []

    try:
        for file in files:
            display_name = upload_display_name(file.filename)
            try:
                filename = safe_upload_filename(file.filename or "", supported_extensions)
            except ValueError as exc:
                skipped.append({"filename": display_name, "reason": str(exc)})
                continue

            if filename in seen_names:
                skipped.append({"filename": display_name, "reason": f"duplicate file name: {filename}"})
                continue
            seen_names.add(filename)

            destination = os.path.abspath(os.path.join(training_dir, filename))
            if not destination.startswith(training_root + os.sep):
                raise ValueError("Upload destination is outside the training directory.")
            if os.path.exists(destination) and not overwrite:
                skipped.append({"filename": filename, "reason": "already exists"})
                continue

            tmp_path = os.path.join(training_dir, f".{filename}.{uuid.uuid4().hex}.upload")
            prepared.append((file, filename, destination, tmp_path))
            tmp_paths.append(tmp_path)

        for file, filename, destination, tmp_path in prepared:
            bytes_written = 0
            with open(tmp_path, "wb") as out_file:
                while True:
                    chunk = await file.read(1024 * 1024)
                    if not chunk:
                        break
                    bytes_written += len(chunk)
                    out_file.write(chunk)
            if bytes_written <= 0:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                skipped.append({"filename": filename, "reason": "empty file"})
                continue
            uploaded.append({
                "filename": filename,
                "destination": destination,
                "tmpPath": tmp_path,
                "bytes": bytes_written,
            })

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
