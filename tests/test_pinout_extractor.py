import unittest

from pinout_extractor import extract_pinout_map


class PinoutExtractorTests(unittest.TestCase):
    def test_extracts_compact_4n35_pinout(self):
        chunks = [
            "Optocoupler, Phototransistor Output\n1 2 3 6 5 4 B C E A C NC",
        ]
        metadata = [{"source": "training/4n35.pdf", "page": 2}]

        pinout = extract_pinout_map(chunks, metadata, "training/4n35.pdf")

        self.assertEqual(
            [(pin["pin"], pin["function"]) for pin in pinout["pins"]],
            [
                (1, "Anode"),
                (2, "Cathode"),
                (3, "No connection"),
                (4, "Emitter"),
                (5, "Collector"),
                (6, "Base"),
            ],
        )

    def test_extracts_direct_pin_lines(self):
        chunks = ["Pin 1: VCC\nPin 2: GND"]
        metadata = [{"source": "timer.pdf", "page": 1}]

        pinout = extract_pinout_map(chunks, metadata, "timer.pdf")

        self.assertEqual(len(pinout["pins"]), 2)
        self.assertEqual(pinout["pins"][0]["function"], "VCC")
        self.assertEqual(pinout["pins"][1]["function"], "Ground")

    def test_extracts_datasheet_pin_description_table(self):
        chunks = [
            """PIN CONFIGURATIONS
PIN DESCRIPTIONS
DEVICE
ANALOG/
DIGITAL
INPUT/
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
2
NC(1)
ALERT/RDY
ALERT/RDY
Digital Output
Digital comparator output or conversion ready
3
GND
GND
GND
Analog
Ground
8
VDD
VDD
VDD
Analog
Power supply: 2.0V to 5.5V
9
SDA
SDA
SDA
Digital I/O
Serial data
10
SCL
SCL
SCL
Digital Input
Serial clock input"""
        ]
        metadata = [{"source": "ads1115.pdf", "page": 4}]

        pinout = extract_pinout_map(chunks, metadata, "ads1115.pdf")

        self.assertEqual(
            [(pin["pin"], pin["function"], pin["page"]) for pin in pinout["pins"]],
            [
                (1, "ADDR", 4),
                (2, "ALERT/RDY", 4),
                (3, "Ground", 4),
                (8, "VDD", 4),
                (9, "SDA", 4),
                (10, "SCL", 4),
            ],
        )

    def test_extracts_ordered_pin_function_sequence_when_numbers_are_split_out(self):
        chunks = [
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
        ]
        metadata = [
            {"source": "timer.pdf", "page": 3},
            {"source": "timer.pdf", "page": 3},
            {"source": "timer.pdf", "page": 3},
        ]

        pinout = extract_pinout_map(chunks, metadata, "timer.pdf")

        self.assertEqual(
            [(pin["pin"], pin["function"], pin["page"]) for pin in pinout["pins"]],
            [
                (1, "Ground", 3),
                (2, "Trigger input", 3),
                (3, "Output", 3),
                (4, "Reset", 3),
                (5, "VCC", 3),
                (6, "Discharge", 3),
                (7, "Threshold input", 3),
                (8, "Control voltage", 3),
            ],
        )

    def test_ordered_sequence_requires_pin_function_page_context(self):
        chunks = ["GND\nTRIG\nOUT\nRESET\nVCC\nDISCH\nTHRES\nCONT"]
        metadata = [{"source": "timer.pdf", "page": 1}]

        pinout = extract_pinout_map(chunks, metadata, "timer.pdf")

        self.assertEqual(pinout["pins"], [])


if __name__ == "__main__":
    unittest.main()
