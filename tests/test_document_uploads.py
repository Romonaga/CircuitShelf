import asyncio
from io import BytesIO

from fastapi import UploadFile

from backend.api.documents import write_uploaded_documents


def upload_file(filename: str, content: bytes) -> UploadFile:
    return UploadFile(BytesIO(content), filename=filename)


def test_batch_upload_skips_unsupported_files_without_blocking_valid_files(tmp_path):
    result = asyncio.run(
        write_uploaded_documents(
            [
                upload_file("books/timers/ne555.pdf", b"%PDF test"),
                upload_file("books/timers/metadata.json", b'{"not": "a document"}'),
            ],
            overwrite=False,
            training_dir=str(tmp_path),
            supported_extensions={".pdf", ".txt"},
        )
    )

    assert result["uploaded"] == [{"filename": "ne555.pdf", "bytes": 9}]
    assert result["skipped"] == [
        {
            "filename": "books/timers/metadata.json",
            "reason": "Unsupported file type. Allowed: .pdf, .txt",
        }
    ]
    assert (tmp_path / "ne555.pdf").read_bytes() == b"%PDF test"
    assert not (tmp_path / "metadata.json").exists()


def test_batch_upload_skips_duplicate_basenames_and_empty_files(tmp_path):
    result = asyncio.run(
        write_uploaded_documents(
            [
                upload_file("first/ne555.pdf", b"%PDF test"),
                upload_file("second/ne555.pdf", b"%PDF duplicate"),
                upload_file("empty.txt", b""),
            ],
            overwrite=False,
            training_dir=str(tmp_path),
            supported_extensions={".pdf", ".txt"},
        )
    )

    assert result["uploaded"] == [{"filename": "ne555.pdf", "bytes": 9}]
    assert result["skipped"] == [
        {"filename": "second/ne555.pdf", "reason": "duplicate file name: ne555.pdf"},
        {"filename": "empty.txt", "reason": "empty file"},
    ]
    assert (tmp_path / "ne555.pdf").read_bytes() == b"%PDF test"
    assert not list(tmp_path.glob("*.upload"))
