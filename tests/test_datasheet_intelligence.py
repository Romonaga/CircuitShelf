import unittest

from circuit_build_cards import build_circuit_build_card, should_build_card
from datasheet_intelligence import build_datasheet_intelligence
from backend.ingestion.document_classifier import classify_document
from backend.ingestion.models import ExtractedPage


class DatasheetIntelligenceTests(unittest.TestCase):
    def test_reference_book_does_not_become_fake_component(self):
        chunks = [
            "FreeCAD for Makers EDITOR Andrew Gregory FreeCAD is not playing catch-up with some paid-for application.",
            "Create 3D prints, laser cuts, folded sheets, and more with free design software.",
            "CHAPTER 1 Introduction to modelling and practical workshop projects.",
        ]
        metadata = [
            {"source": "FreeCAD for Makers.pdf", "parent_source": "FreeCAD for Makers.pdf", "page": 1},
            {"source": "FreeCAD for Makers.pdf", "parent_source": "FreeCAD for Makers.pdf", "page": 3},
            {"source": "FreeCAD for Makers.pdf", "parent_source": "FreeCAD for Makers.pdf", "page": 4},
        ]

        intelligence = build_datasheet_intelligence(chunks, metadata, "FreeCAD for Makers.pdf", "FreeCAD for Makers.pdf")

        self.assertEqual(intelligence["componentName"], "")
        self.assertEqual(intelligence["facts"], [])
        self.assertEqual(intelligence["pinout"]["pins"], [])

    def test_classifier_detects_component_datasheet(self):
        profile = classify_document(
            "ESP32 datasheet.pdf",
            [
                ExtractedPage(
                    page_number=1,
                    text=(
                        "ESP32 Series Datasheet Features Pin Definitions Electrical Characteristics "
                        "Absolute Maximum Ratings Recommended Operating Conditions."
                    ),
                )
            ],
        )

        self.assertEqual(profile.document_type, "component_datasheet")
        self.assertEqual(profile.component_name, "ESP32")
        self.assertEqual(profile.component_type, "microcontroller")

    def test_classifier_prefers_driver_part_over_datasheet_order_code(self):
        profile = classify_document(
            "ST L298 dual full-bridge driver datasheet.pdf",
            [
                ExtractedPage(
                    page_number=1,
                    text=(
                        "L298 dual full-bridge driver datasheet. Pin connection, electrical "
                        "characteristics, absolute maximum ratings, Multiwatt15, PowerSO20. "
                        "STMicroelectronics order code DS0218."
                    ),
                )
            ],
        )

        self.assertEqual(profile.document_type, "component_datasheet")
        self.assertEqual(profile.component_name, "L298")
        self.assertEqual(profile.component_type, "motor driver")

    def test_beginner_project_recommendation_does_not_trigger_build_card(self):
        self.assertFalse(should_build_card("what is a good beginer project."))

        unrelated_intelligence = {
            "source": "mosfet.pdf",
            "displayName": "mosfet.pdf",
            "componentName": "MOSFET",
            "componentType": "transistor",
            "summary": "Detected transistor details.",
            "confidence": 0.8,
            "facts": [],
            "pinout": {"pins": [{"pin": 1, "function": "Gate", "page": 2}]},
        }

        card = build_circuit_build_card(
            "what is a good beginner project",
            [{"source": "training/mosfet.pdf", "displayName": "mosfet.pdf", "pages": [2], "chunkCount": 1}],
            {"training/mosfet.pdf": unrelated_intelligence},
        )

        self.assertIsNone(card)

    def test_specific_build_request_triggers_build_card(self):
        self.assertTrue(should_build_card("build a 555 timer blinking LED"))
        self.assertTrue(should_build_card("wire a 4n35 to an arduino"))
        self.assertTrue(should_build_card("give me a build card"))
        self.assertTrue(should_build_card("make a beginner 555 project and include a build card"))

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

    def test_build_card_prefers_matching_555_component_over_noisy_source_match(self):
        noisy_project_book = {
            "questionMatch": True,
            "source": "training/Engineer's Mini-Notebook - 555 Timer Circuits.pdf",
            "displayName": "Engineer's Mini-Notebook - 555 Timer Circuits.pdf",
            "componentName": "NEAQ",
            "componentType": "timer",
            "summary": "NEAQ appears to be a timer.",
            "confidence": 0.75,
            "facts": [],
            "pinout": {"pins": []},
        }
        datasheet = {
            "questionMatch": True,
            "source": "training/ne555.pdf",
            "displayName": "ne555.pdf",
            "componentName": "NE555",
            "componentType": "timer",
            "summary": "NE555 appears to be a timer.",
            "confidence": 0.75,
            "facts": [],
            "pinout": {"pins": []},
        }

        card = build_circuit_build_card(
            "build me a 555 timer project that is hooked up to an arduino",
            [
                {"source": "training/Engineer's Mini-Notebook - 555 Timer Circuits.pdf"},
                {"source": "training/ne555.pdf"},
            ],
            {
                "training/Engineer's Mini-Notebook - 555 Timer Circuits.pdf": noisy_project_book,
                "training/ne555.pdf": datasheet,
            },
        )

        self.assertEqual(card["componentName"], "NE555")

    def test_followup_build_card_uses_conversation_context_for_component(self):
        mosfet = {
            "source": "training/mosfet.pdf",
            "displayName": "mosfet.pdf",
            "componentName": "MOSFET",
            "componentType": "transistor",
            "summary": "",
            "confidence": 0.7,
            "facts": [],
            "pinout": {"pins": []},
        }
        timer = {
            "source": "training/ne555.pdf",
            "displayName": "ne555.pdf",
            "componentName": "NE555",
            "componentType": "timer",
            "summary": "NE555 timer.",
            "confidence": 0.9,
            "facts": [],
            "pinout": {"pins": [{"pin": 1, "function": "GND", "page": 2}]},
        }

        card = build_circuit_build_card(
            "give me a build card",
            [
                {"source": "training/mosfet.pdf"},
                {"source": "training/ne555.pdf"},
            ],
            {
                "training/mosfet.pdf": mosfet,
                "training/ne555.pdf": timer,
            },
            context_question="Previous user question: what is a good beginner project with a 555 timer?\nCurrent user question: give me a build card",
        )

        self.assertIsNotNone(card)
        self.assertEqual(card["componentName"], "NE555")

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

    def test_timer_datasheet_uses_generic_pin_function_sequence_without_application_noise(self):
        chunks = [
            "NE555 Precision Timer Datasheet Pin Functions Electrical Characteristics Recommended Operating Conditions",
            """GND
TRIG
OUT
RESET
VCC
DISCH
THRES
CONT
NC
DISCH
NC
THRES
NC
NC
TRIG
NC
OUT
NC
NC
GND
NC
CONT
NC
VCC
NC
NC
RESET
NC
NC - No internal connection""",
            """Pin Functions
PIN
D, P, PS,
FK
I/O""",
            """PW, JG
NAME
NO.
Controls comparator thresholds, Outputs 2/3 VCC, allows bypass capacitor
CONT
I/O
connection
DISCH
O
Open collector output to discharge timing capacitor
GND
Ground
NC
No internal connection
OUT
O
High current timer output signal
RESET
I
Active low reset input forces output and discharge low.
THRES
I
End of timing input. THRES > CONT sets output low and discharge low
TRIG
I
Start of timing input. TRIG < 1/2 CONT sets output high and discharge open
VCC
Input supply voltage, 4.5 V to 16 V.""",
            "Applications Simplified schematic information is not part of the TI component specification.",
        ]
        metadata = [
            {"source": "ne555.pdf", "parent_source": "ne555.pdf", "page": 1},
            {"source": "ne555.pdf", "parent_source": "ne555.pdf", "page": 3},
            {"source": "ne555.pdf", "parent_source": "ne555.pdf", "page": 3},
            {"source": "ne555.pdf", "parent_source": "ne555.pdf", "page": 3},
            {"source": "ne555.pdf", "parent_source": "ne555.pdf", "page": 13},
        ]

        intelligence = build_datasheet_intelligence(chunks, metadata, "ne555.pdf", "ne555.pdf")

        self.assertEqual(intelligence["componentName"], "NE555")
        self.assertEqual(len(intelligence["pinout"]["pins"]), 8)
        self.assertEqual(
            [(pin["pin"], pin["function"]) for pin in intelligence["pinout"]["pins"]],
            [
                (1, "Ground"),
                (2, "Trigger input"),
                (3, "Output"),
                (4, "Reset"),
                (5, "VCC"),
                (6, "Discharge"),
                (7, "Threshold input"),
                (8, "Control voltage"),
            ],
        )
        self.assertNotIn("application", {fact["type"] for fact in intelligence["facts"]})

    def test_voltage_range_suppresses_redundant_single_supply_conditions(self):
        chunks = [
            """SN74HC04 Hex Inverter Datasheet
Features Pin Functions Electrical Characteristics Absolute Maximum Ratings
Recommended Operating Conditions
Operating voltage is 2 V to 6 V.
Supply voltage test condition 2 V.
Supply voltage test condition 4.5 V.""",
            """1A
1Y
2A
2Y
3A
3Y
GND
6A
6Y
5A
5Y
4A
VCC
4Y
Pin Functions
PIN
NAME
1A Input
1Y Output
2A Input
2Y Output
3A Input
3Y Output
GND Ground
6A Input
6Y Output
5A Input
5Y Output
4A Input
VCC Positive Supply
4Y Output""",
        ]
        metadata = [
            {"source": "sn74hc04.pdf", "parent_source": "sn74hc04.pdf", "page": 1},
            {"source": "sn74hc04.pdf", "parent_source": "sn74hc04.pdf", "page": 3},
        ]

        intelligence = build_datasheet_intelligence(chunks, metadata, "sn74hc04.pdf", "sn74hc04.pdf")

        voltage_facts = [fact for fact in intelligence["facts"] if fact["type"] == "voltage"]
        self.assertEqual([(fact["label"], fact["value"]) for fact in voltage_facts], [("OPERATING VOLTAGE", "2 to 6")])

    def test_warning_facts_skip_legal_and_ordering_notes(self):
        chunks = [
            """LM555 timer datasheet Pin Functions Electrical Characteristics
Stresses beyond those listed under Absolute Maximum Ratings may cause permanent damage to the device.
TI disclaims responsibility, and you will fully indemnify TI and its representatives against any claims, damages, costs, losses, and liabilities arising out of your use of the device.
RoHS compliance indicates package option addendum ordering information.""",
            """GND
TRIGGER
OUTPUT
RESET
VCC
DISCHARGE
THRESHOLD
CONTROL
VOLTAGE
Pin Functions
PIN
NAME
GND Ground
Trigger Input
Output Output
Reset Reset
VCC Supply voltage
Discharge Discharge
Threshold Threshold
Control Voltage Control voltage""",
        ]
        metadata = [
            {"source": "lm555.pdf", "parent_source": "lm555.pdf", "page": 4},
            {"source": "lm555.pdf", "parent_source": "lm555.pdf", "page": 3},
        ]

        intelligence = build_datasheet_intelligence(chunks, metadata, "lm555.pdf", "lm555.pdf")

        warning_values = [fact["value"] for fact in intelligence["facts"] if fact["type"] == "warning"]
        self.assertEqual(len(warning_values), 1)
        self.assertIn("permanent damage", warning_values[0])
        self.assertFalse(any("disclaims responsibility" in value for value in warning_values))


if __name__ == "__main__":
    unittest.main()
