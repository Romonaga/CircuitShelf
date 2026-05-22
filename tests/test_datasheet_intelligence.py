import unittest

from circuit_build_cards import build_circuit_build_card
from datasheet_intelligence import build_datasheet_intelligence


class DatasheetIntelligenceTests(unittest.TestCase):
    def test_extracts_component_facts_and_pinout(self):
        chunks = [
            "4N35 optocoupler isolation device. Supply voltage 3 to 30 V. DIP-6 package.",
            "1 2 3 6 5 4 B C E A C NC",
        ]
        metadata = [
            {"source": "training/4n35.pdf", "parent_source": "training/4n35.pdf", "page": 1},
            {"source": "training/4n35.pdf", "parent_source": "training/4n35.pdf", "page": 2},
        ]

        intelligence = build_datasheet_intelligence(chunks, metadata, "training/4n35.pdf", "4n35.pdf")

        self.assertEqual(intelligence["componentName"], "4N35")
        self.assertEqual(intelligence["componentType"], "optocoupler")
        self.assertTrue(any(fact["type"] == "voltage" for fact in intelligence["facts"]))
        self.assertEqual(len(intelligence["pinout"]["pins"]), 6)

    def test_build_card_uses_optocoupler_pinout(self):
        intelligence = {
            "source": "4n35.pdf",
            "displayName": "4n35.pdf",
            "componentName": "4N35",
            "componentType": "optocoupler",
            "summary": "Detected 6 pin assignments.",
            "confidence": 0.9,
            "facts": [],
            "pinout": {
                "pins": [
                    {"pin": 1, "function": "Anode", "page": 2},
                    {"pin": 2, "function": "Cathode", "page": 2},
                ]
            },
        }

        card = build_circuit_build_card(
            "wire a 4n35 to an arduino",
            [{"source": "training/4n35.pdf", "displayName": "4n35.pdf", "pages": [2], "chunkCount": 2}],
            {"training/4n35.pdf": intelligence},
        )

        self.assertIsNotNone(card)
        self.assertEqual(card["componentName"], "4N35")
        self.assertTrue(any(row["from"].startswith("Pin 1") for row in card["wiring"]))

    def test_build_card_prefers_question_component_over_retrieved_source(self):
        preferred = {
            "questionMatch": True,
            "source": "4n35.pdf",
            "displayName": "4n35.pdf",
            "componentName": "4N35",
            "componentType": "optocoupler",
            "summary": "",
            "confidence": 0.9,
            "facts": [],
            "pinout": {"pins": []},
        }
        retrieved = {
            "source": "100_ic.pdf",
            "displayName": "100_ic.pdf",
            "componentName": "NEON",
            "componentType": "component",
            "summary": "",
            "confidence": 0.5,
            "facts": [],
            "pinout": {"pins": []},
        }

        card = build_circuit_build_card(
            "wire a 4n35 to an arduino",
            [{"source": "training/100_ic.pdf", "displayName": "100_ic.pdf", "pages": [1], "chunkCount": 1}],
            {"training/4n35.pdf": preferred, "training/100_ic.pdf": retrieved},
        )

        self.assertEqual(card["componentName"], "4N35")

    def test_ads_datasheet_is_detected_as_adc_with_pinout(self):
        chunks = [
            """ADS1115
16-Bit Analog-to-Digital Converter
PIN CONFIGURATIONS
PIN DESCRIPTIONS
PIN #
ADS1113
ADS1114
ADS1115
OUTPUT
DESCRIPTION
1
ADDR
ADDR
ADDR
Digital Input
I2C slave address select
8
VDD
VDD
VDD
Analog
Power supply: 2.0V to 5.5V
10
SCL
SCL
SCL
Digital Input
Serial clock input"""
        ]
        metadata = [{"source": "ads1115.pdf", "parent_source": "ads1115.pdf", "page": 4}]

        intelligence = build_datasheet_intelligence(chunks, metadata, "ads1115.pdf", "ads1115.pdf")

        self.assertEqual(intelligence["componentName"], "ADS1115")
        self.assertEqual(intelligence["componentType"], "analog-to-digital converter")
        self.assertEqual(
            [(pin["pin"], pin["function"]) for pin in intelligence["pinout"]["pins"]],
            [(1, "ADDR"), (8, "VDD"), (10, "SCL")],
        )


if __name__ == "__main__":
    unittest.main()
