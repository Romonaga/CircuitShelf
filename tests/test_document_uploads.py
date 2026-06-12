import asyncio
import shutil
import subprocess
import zipfile
from io import BytesIO

from fastapi import UploadFile
import pytest

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

    assert result["uploaded"] == [{"filename": "books/timers/ne555.pdf", "bytes": 9}]
    assert result["skipped"] == [
        {
            "filename": "books/timers/metadata.json",
            "reason": "Unsupported file type. Allowed: .pdf, .txt",
        }
    ]
    assert (tmp_path / "books" / "timers" / "ne555.pdf").read_bytes() == b"%PDF test"
    assert not (tmp_path / "metadata.json").exists()


def test_batch_upload_preserves_folders_and_skips_duplicate_paths_and_empty_files(tmp_path):
    result = asyncio.run(
        write_uploaded_documents(
            [
                upload_file("first/ne555.pdf", b"%PDF test"),
                upload_file("second/ne555.pdf", b"%PDF second"),
                upload_file("first/ne555.pdf", b"%PDF duplicate"),
                upload_file("empty.txt", b""),
            ],
            overwrite=False,
            training_dir=str(tmp_path),
            supported_extensions={".pdf", ".txt"},
        )
    )

    assert result["uploaded"] == [
        {"filename": "first/ne555.pdf", "bytes": 9},
        {"filename": "second/ne555.pdf", "bytes": 11},
    ]
    assert result["skipped"] == [
        {"filename": "first/ne555.pdf", "reason": "duplicate file path: first/ne555.pdf"},
        {"filename": "empty.txt", "reason": "empty file"},
    ]
    assert (tmp_path / "first" / "ne555.pdf").read_bytes() == b"%PDF test"
    assert (tmp_path / "second" / "ne555.pdf").read_bytes() == b"%PDF second"
    assert not list(tmp_path.rglob("*.upload"))


def test_batch_upload_rejects_path_traversal(tmp_path):
    result = asyncio.run(
        write_uploaded_documents(
            [upload_file("../bad/evil.ino", b"void setup() {}")],
            overwrite=False,
            training_dir=str(tmp_path),
            supported_extensions={".ino"},
        )
    )

    assert result["uploaded"] == []
    assert result["skipped"] == [{"filename": "../bad/evil.ino", "reason": "Upload file name is not allowed."}]


def test_code_sample_upload_accepts_common_project_folder_characters(tmp_path):
    result = asyncio.run(
        write_uploaded_documents(
            [
                upload_file("Bob's Arduino [test] #1/examples/blink-test/blink-test.ino", b"void setup() {}"),
                upload_file("Bob's Arduino [test] #1/src/sensor-map.cpp", b"int sensorPin = A0;"),
            ],
            overwrite=False,
            training_dir=str(tmp_path),
            supported_extensions={".ino", ".cpp"},
        )
    )

    assert result["uploaded"] == [
        {
            "filename": "Bob's Arduino [test] #1/examples/blink-test/blink-test.ino",
            "bytes": 15,
        },
        {
            "filename": "Bob's Arduino [test] #1/src/sensor-map.cpp",
            "bytes": 19,
        },
    ]
    assert result["skipped"] == []
    assert (tmp_path / "Bob's Arduino [test] #1" / "examples" / "blink-test" / "blink-test.ino").read_bytes() == b"void setup() {}"
    assert (tmp_path / "Bob's Arduino [test] #1" / "src" / "sensor-map.cpp").read_bytes() == b"int sensorPin = A0;"


def test_code_sample_upload_accepts_extensionless_shell_script(tmp_path):
    result = asyncio.run(
        write_uploaded_documents(
            [upload_file("RaspberryPi/sim7080g_cat_m_nb_iot_hat_init", b"#!/bin/sh\necho init")],
            overwrite=False,
            training_dir=str(tmp_path),
            supported_extensions={".sh"},
        )
    )

    assert result["uploaded"] == [
        {
            "filename": "RaspberryPi/sim7080g_cat_m_nb_iot_hat_init.sh",
            "bytes": 19,
        }
    ]
    assert result["skipped"] == []
    assert (tmp_path / "RaspberryPi" / "sim7080g_cat_m_nb_iot_hat_init.sh").read_bytes() == b"#!/bin/sh\necho init"


def test_zip_upload_expands_supported_code_and_ignores_project_internals(tmp_path):
    archive = BytesIO()
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("Arduino/Demo/demo.ino", b"void setup() {}")
        bundle.writestr("scripts/pi_gpio_init.sh", b"#!/bin/sh\necho gpio")
        bundle.writestr("scripts/init", b"#!/bin/sh\necho init")
        bundle.writestr("Drivers/CMSIS/Include/core_cm3.h", b"#define CMSIS_VENDOR 1")
        bundle.writestr("Drivers/STM32F1xx_HAL_Driver/Inc/stm32f1xx_hal_gpio.h", b"#define HAL_VENDOR 1")
        bundle.writestr("MDK-ARM/RTE/_Demo/RTE_Components.h", b"#define IDE_GENERATED 1")
        bundle.writestr(".git/config", b"[core]\nrepositoryformatversion = 0")
        bundle.writestr("notes.tmp", b"ignore")
    archive.seek(0)

    result = asyncio.run(
        write_uploaded_documents(
            [upload_file("SIM7080G_Cat_M_NB_IoT_HAT_Code/source_bundle.zip", archive.getvalue())],
            overwrite=False,
            training_dir=str(tmp_path),
            supported_extensions={".ino", ".sh"},
        )
    )

    assert result["uploaded"] == [
        {
            "filename": "SIM7080G_Cat_M_NB_IoT_HAT_Code/Arduino/Demo/demo.ino",
            "bytes": 15,
        },
        {
            "filename": "SIM7080G_Cat_M_NB_IoT_HAT_Code/scripts/init.sh",
            "bytes": 19,
        },
        {
            "filename": "SIM7080G_Cat_M_NB_IoT_HAT_Code/scripts/pi_gpio_init.sh",
            "bytes": 19,
        },
    ]
    assert (tmp_path / "SIM7080G_Cat_M_NB_IoT_HAT_Code" / "Arduino" / "Demo" / "demo.ino").read_bytes() == b"void setup() {}"
    assert (tmp_path / "SIM7080G_Cat_M_NB_IoT_HAT_Code" / "scripts" / "init.sh").read_bytes() == b"#!/bin/sh\necho init"
    assert (tmp_path / "SIM7080G_Cat_M_NB_IoT_HAT_Code" / "scripts" / "pi_gpio_init.sh").read_bytes() == b"#!/bin/sh\necho gpio"
    assert not (tmp_path / "SIM7080G_Cat_M_NB_IoT_HAT_Code" / ".git").exists()
    assert not (tmp_path / "SIM7080G_Cat_M_NB_IoT_HAT_Code" / "Drivers" / "CMSIS").exists()
    assert not (tmp_path / "SIM7080G_Cat_M_NB_IoT_HAT_Code" / "Drivers" / "STM32F1xx_HAL_Driver").exists()
    assert not (tmp_path / "SIM7080G_Cat_M_NB_IoT_HAT_Code" / "MDK-ARM").exists()
    assert any(item["reason"] == "ignored project/internal file" for item in result["skipped"])
    assert any(item["reason"] == "ignored generated/vendor dependency file" for item in result["skipped"])
    assert any("Unsupported file type" in item["reason"] for item in result["skipped"])


def test_7z_upload_expands_supported_code_when_7z_is_installed(tmp_path):
    seven_zip = shutil.which("7z")
    if not seven_zip:
        pytest.skip("7z command is not installed")
    source_dir = tmp_path / "archive_source"
    source_dir.mkdir()
    main_code = b"void setup() {}"
    driver_code = b"int modemPowerPin = 5;"
    (source_dir / "main.ino").write_bytes(main_code)
    (source_dir / "driver.cpp").write_bytes(driver_code)
    archive_path = tmp_path / "demo.7z"
    subprocess.run(
        [seven_zip, "a", "-bd", "-bb0", str(archive_path), "main.ino", "driver.cpp"],
        check=True,
        cwd=str(source_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    result = asyncio.run(
        write_uploaded_documents(
            [upload_file("SIM7080G_Cat_M_NB_IoT_HAT_Code/STM32/SIM7080G_TCP_Test_Demo.7z", archive_path.read_bytes())],
            overwrite=False,
            training_dir=str(tmp_path / "training"),
            supported_extensions={".cpp", ".ino"},
        )
    )

    assert result["uploaded"] == [
        {
            "filename": "SIM7080G_Cat_M_NB_IoT_HAT_Code/STM32/driver.cpp",
            "bytes": len(driver_code),
        },
        {
            "filename": "SIM7080G_Cat_M_NB_IoT_HAT_Code/STM32/main.ino",
            "bytes": len(main_code),
        },
    ]
