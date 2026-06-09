from backend.services.document_intelligence_service import DocumentIntelligenceService, merge_datasheet_repair


def test_datasheet_repair_fills_missing_pinout_without_losing_local_facts():
    local = {
        "componentName": "LM555",
        "componentType": "timer",
        "summary": "LM555 appears to be a timer.",
        "confidence": 0.75,
        "facts": [
            {"type": "voltage", "label": "VCC", "value": "5 to 15", "unit": "V", "page": 5},
        ],
        "pinout": {"pins": []},
    }
    repair = {
        "confidence": 0.93,
        "pinout": {
            "pins": [
                {"pin": 1, "label": "GND", "function": "Ground", "page": 3, "evidence": "Pin 1 GND"},
                {"pin": 2, "label": "TRIGGER", "function": "Trigger input", "page": 3, "evidence": "Pin 2 Trigger"},
                {"pin": 3, "label": "OUTPUT", "function": "Output", "page": 3, "evidence": "Pin 3 Output"},
            ]
        },
        "facts": [
            {"type": "package", "label": "Package", "value": "PDIP", "unit": "", "page": 3},
        ],
    }

    merged = merge_datasheet_repair(local, repair)

    assert len(merged["pinout"]["pins"]) == 3
    assert merged["facts"][0]["label"] == "VCC"
    assert any(fact["value"] == "PDIP" for fact in merged["facts"])
    assert merged["confidence"] == 0.93


def test_datasheet_repair_does_not_replace_stronger_local_pinout():
    local = {
        "componentName": "NE555",
        "componentType": "timer",
        "confidence": 0.97,
        "facts": [],
        "pinout": {
            "pins": [
                {"pin": 1, "label": "GND", "function": "Ground"},
                {"pin": 2, "label": "TRIG", "function": "Trigger input"},
                {"pin": 3, "label": "OUT", "function": "Output"},
                {"pin": 4, "label": "RESET", "function": "Reset"},
            ]
        },
    }
    repair = {
        "confidence": 0.9,
        "pinout": {
            "pins": [
                {"pin": 1, "label": "GND", "function": "Ground"},
                {"pin": 3, "label": "OUT", "function": "Output"},
                {"pin": 4, "label": "RESET", "function": "Reset"},
            ]
        },
    }

    merged = merge_datasheet_repair(local, repair)

    assert [pin["pin"] for pin in merged["pinout"]["pins"]] == [1, 2, 3, 4]
    assert merged["confidence"] == 0.97


def test_stored_datasheet_intelligence_with_store_version_is_usable():
    stored = {
        "componentName": "ESP32",
        "componentType": "microcontroller",
        "confidence": 0.91,
        "extractorVersion": 2,
        "facts": [],
        "pinout": {"pins": [{"pin": 1, "label": "GND", "function": "Ground"}]},
    }

    assert DocumentIntelligenceService.stored_is_usable(stored)
