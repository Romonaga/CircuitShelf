import logging

from backend.ingestion.code_samples import (
    annotated_code_text,
    code_sample_metadata,
    is_code_sample_companion_path,
    safe_relative_upload_path,
)
from backend.ingestion.document_classifier import classify_document
from backend.ingestion.document_extractors import DocumentExtractor
from backend.ingestion.document_state_writer import DocumentStateWriter
from backend.ingestion.models import ExtractedDocument, ExtractedPage


class FakeState:
    def __init__(self):
        self.chunks = []
        self.sources = []
        self.metadata = []

    def extend_chunks(self, chunks, sources, metadata):
        self.chunks.extend(chunks)
        self.sources.extend(sources)
        self.metadata.extend(metadata)

    def add_image_store(self, *_args):
        raise AssertionError("No images expected")


class FakeChunker:
    def smart_chunk_pages(self, page_texts, source_file):
        return page_texts, [{"section": "Source", "category": "General Information", "quality_score": 0.4, "quality_flags": ["symbol_heavy"]}]


class FakeTokenUtils:
    @staticmethod
    def estimate_token_density(_text):
        return 4


def test_safe_relative_upload_path_preserves_pack_folder():
    assert safe_relative_upload_path("blink/Blink.ino", {".ino"}) == "blink/Blink.ino"


def test_code_sample_metadata_extracts_electronics_context():
    text = """
    #include <Wire.h>
    #include <Adafruit_SSD1306.h>
    const int ledPin = 13;
    void setup() { Serial.begin(115200); Wire.begin(); pinMode(ledPin, OUTPUT); }
    void loop() { digitalWrite(ledPin, HIGH); }
    """

    meta = code_sample_metadata("oled-blink/Blink.ino", text)

    assert meta["code_pack"] == "oled-blink"
    assert meta["code_language"] == "Arduino"
    assert meta["code_framework"] == "Arduino"
    assert "I2C" in meta["code_interfaces"]
    assert "GPIO" in meta["code_interfaces"]
    assert "Adafruit_SSD1306" in meta["code_libraries"]
    assert "Serial baud 115200" in meta["code_serial_settings"]
    assert any(pin["name"] == "ledPin" and pin["pin"] == "13" for pin in meta["code_pins"])


def test_code_sample_metadata_extracts_at_commands_generically():
    meta = code_sample_metadata(
        "modem/main.cpp",
        'Serial1.begin(9600);\nmodem.println("AT+CGATT=1");\nmodem.println("AT+CSQ");',
    )

    assert "Serial baud 9600" in meta["code_serial_settings"]
    assert "AT+CGATT=1" in meta["code_at_commands"]
    assert "AT+CSQ" in meta["code_at_commands"]


def test_code_sample_metadata_extracts_go_rust_and_react_context():
    go_meta = code_sample_metadata(
        "tinygo-blink/main.go",
        'package main\nimport "machine"\nconst ledPin = machine.GPIO13\nfunc main() { machine.UART0.Configure(machine.UARTConfig{}) }',
    )
    rust_meta = code_sample_metadata(
        "rust-blink/src/main.rs",
        "use embedded_hal::digital::OutputPin;\nconst LED_PIN: u8 = 25;\nlet led = Pin::new(25);",
    )
    react_meta = code_sample_metadata(
        "serial-console/src/App.tsx",
        "import React, { useEffect } from 'react';\nconst resetPin: number = 4;\nawait navigator.serial.requestPort();",
    )

    assert go_meta["code_language"] == "Go"
    assert go_meta["code_framework"] == "TinyGo"
    assert "machine" in go_meta["code_libraries"]
    assert any(pin["pin"] == "13" for pin in go_meta["code_pins"])
    assert rust_meta["code_language"] == "Rust"
    assert rust_meta["code_framework"] == "Rust embedded"
    assert "embedded_hal" in rust_meta["code_libraries"]
    assert any(pin["name"] == "LED_PIN" and pin["pin"] == "25" for pin in rust_meta["code_pins"])
    assert react_meta["code_language"] == "React TSX"
    assert react_meta["code_framework"] == "React"
    assert "react" in [library.lower() for library in react_meta["code_libraries"]]
    assert "WebSerial" in react_meta["code_interfaces"]
    assert any(pin["name"] == "resetPin" and pin["pin"] == "4" for pin in react_meta["code_pins"])


def test_code_sample_companion_detects_readme_with_code_markers():
    text = "Arduino setup uses Serial.begin(115200), pinMode, and AT+CSQ checks."

    assert is_code_sample_companion_path("SIM7080G_Cat_M_NB_IoT_HAT_Code/README.md", text)
    assert not is_code_sample_companion_path("books/timers/README.md", "Published by Example Press.")


def test_code_sample_companion_detects_go_mod_and_react_package_manifest():
    assert is_code_sample_companion_path("tinygo-blink/go.mod", "module blink\nrequire tinygo.org/x/drivers v0.28.0")
    assert is_code_sample_companion_path("serial-console/package.json", '{"dependencies":{"react":"latest","serialport":"latest"}}')


def test_code_sample_classifier_marks_source_files():
    profile = classify_document(
        "examples/blink/Blink.ino",
        [annotated_code_text("examples/blink/Blink.ino", "void setup() {}\nvoid loop() {}")],
    )

    assert profile.document_type == "code_sample"
    assert profile.component_type == "code sample"


def test_document_extractor_routes_code_companion_as_code_sample(tmp_path):
    readme = tmp_path / "SIM7080G_Cat_M_NB_IoT_HAT_Code" / "README.md"
    readme.parent.mkdir()
    readme.write_text("Arduino setup: Serial.begin(115200), send AT+CSQ, use UART pins.", encoding="utf-8")
    extractor = DocumentExtractor(
        config={},
        trace_logger=logging.getLogger("test"),
        run_ocr=None,
        ocr_worker_count=1,
        current_document_workers=lambda: 0,
        local_gpu_ocr_slots=1,
        detected_cpu_count=lambda: 1,
        reserved_core_count=lambda _count: 0,
        pdf_ext=".pdf",
    )

    document = extractor.extract_by_type(str(readme), chunker=None)

    assert document is not None
    assert document.extra_metadata["code_sample"] is True
    assert document.extra_metadata["code_pack"] == "SIM7080G_Cat_M_NB_IoT_HAT_Code"
    assert "AT+CSQ" in document.extra_metadata["code_at_commands"]


def test_document_extractor_uses_training_relative_code_pack_path(tmp_path):
    training = tmp_path / "training"
    source = training / "SIM7080G_Cat_M_NB_IoT_HAT_Code" / "Arduino" / "SIM7080G_PING_Demo" / "demo.ino"
    source.parent.mkdir(parents=True)
    source.write_text("void setup(){ Serial.begin(115200); }\nvoid loop(){}", encoding="utf-8")
    extractor = DocumentExtractor(
        config={"TRAINING_DIR": str(training)},
        trace_logger=logging.getLogger("test"),
        run_ocr=None,
        ocr_worker_count=1,
        current_document_workers=lambda: 0,
        local_gpu_ocr_slots=1,
        detected_cpu_count=lambda: 1,
        reserved_core_count=lambda _count: 0,
        pdf_ext=".pdf",
    )

    document = extractor.extract_by_type(str(source), chunker=None)

    assert document is not None
    assert document.extra_metadata["code_pack"] == "SIM7080G_Cat_M_NB_IoT_HAT_Code"
    assert document.extra_metadata["code_file"] == "SIM7080G_Cat_M_NB_IoT_HAT_Code/Arduino/SIM7080G_PING_Demo/demo.ino"


def test_document_state_writer_carries_code_metadata_to_chunks():
    text = "const int ledPin = 13;\nvoid setup(){ pinMode(ledPin, OUTPUT); }"
    meta = code_sample_metadata("blink/Blink.ino", text)
    document = ExtractedDocument(
        source_path="blink/Blink.ino",
        pages=[ExtractedPage(page_number=1, text=annotated_code_text("blink/Blink.ino", text, meta))],
        profile=classify_document("blink/Blink.ino", [text]),
        extra_metadata=meta,
    )
    state = FakeState()

    DocumentStateWriter(config={}, trace_logger=logging.getLogger("test")).store_extracted_document(
        document,
        state,
        FakeChunker(),
        FakeTokenUtils(),
    )

    assert state.sources == ["blink/Blink.ino"]
    assert state.metadata[0]["document_type"] == "code_sample"
    assert state.metadata[0]["code_pack"] == "blink"
    assert state.metadata[0]["category"] == "CODE_SAMPLE"
    assert state.metadata[0]["chunk_type"] == "code"
    assert state.metadata[0]["quality_score"] >= 0.75
