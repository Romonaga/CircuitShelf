import os

from backend.ingestion.file_scanner import scan_ingest_folder


class StubLogger:
    def __init__(self):
        self.errors = []

    def error(self, message):
        self.errors.append(message)


def test_scan_ingest_folder_always_recurses_even_if_old_setting_is_false(tmp_path):
    nested = tmp_path / "sample_pack" / "Arduino" / "Demo"
    nested.mkdir(parents=True)
    source = nested / "demo.ino"
    source.write_bytes(b"void setup() {}")

    files = scan_ingest_folder(
        str(tmp_path),
        config={"TRAINING_RECURSIVE": False, "TRAINING_EXCLUDE_DIRS": []},
        pdf_ext=".pdf",
        trace_logger=StubLogger(),
    )

    assert files == [os.path.join("sample_pack", "Arduino", "Demo", "demo.ino")]


def test_scan_ingest_folder_skips_generated_vendor_dependency_trees(tmp_path):
    keep_src = tmp_path / "sample_pack" / "STM32" / "Demo" / "Src"
    keep_inc = tmp_path / "sample_pack" / "STM32" / "Demo" / "Inc"
    cmsis = tmp_path / "sample_pack" / "STM32" / "Demo" / "Drivers" / "CMSIS" / "Include"
    hal = tmp_path / "sample_pack" / "STM32" / "Demo" / "Drivers" / "STM32F1xx_HAL_Driver" / "Inc"
    ide = tmp_path / "sample_pack" / "STM32" / "Demo" / "MDK-ARM" / "RTE"
    for directory in (keep_src, keep_inc, cmsis, hal, ide):
        directory.mkdir(parents=True)
    (keep_src / "main.c").write_bytes(b"int main(void) { return 0; }")
    (keep_inc / "main.h").write_bytes(b"#pragma once")
    (cmsis / "core_cm3.h").write_bytes(b"#define CMSIS_VENDOR 1")
    (hal / "stm32f1xx_hal_gpio.h").write_bytes(b"#define HAL_VENDOR 1")
    (ide / "RTE_Components.h").write_bytes(b"#define IDE_GENERATED 1")

    files = scan_ingest_folder(
        str(tmp_path),
        config={"TRAINING_EXCLUDE_DIRS": []},
        pdf_ext=".pdf",
        trace_logger=StubLogger(),
    )

    assert sorted(files) == sorted([
        os.path.join("sample_pack", "STM32", "Demo", "Src", "main.c"),
        os.path.join("sample_pack", "STM32", "Demo", "Inc", "main.h"),
    ])
