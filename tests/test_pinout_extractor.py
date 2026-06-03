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

    def test_extracts_logic_ic_top_view_sequence_with_split_table(self):
        chunks = [
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
ph Top View
2A
NC
2Y
NC
3A
20-Pin LCCC
Top View
Pin Functions
PIN
I/O""",
            """NAME
D, DB, N,
NS, PW, J,
or W
FK
1A
Input
Channel 1, Input A
1Y
Output
Channel 1, Output Y
2A
Input
Channel 2, Input A
2Y
Output
Channel 2, Output Y
3A
Input
Channel 3, Input A
3Y
Output
Channel 3, Output Y
GND
Ground
4Y
Output
Channel 4, Output Y
4A
Input
Channel 4, Input A
5Y
Output
Channel 5, Output Y
5A
Input
Channel 5, Input A
6Y
Output
Channel 6, Output Y
6A
Input
Channel 6, Input A
VCC
Positive Supply
NC
Not internally connected""",
        ]
        metadata = [
            {"source": "sn74hc04.pdf", "page": 3},
            {"source": "sn74hc04.pdf", "page": 3},
        ]

        pinout = extract_pinout_map(chunks, metadata, "sn74hc04.pdf")

        self.assertEqual(
            [(pin["pin"], pin["function"]) for pin in pinout["pins"]],
            [
                (1, "1A"),
                (2, "1Y"),
                (3, "2A"),
                (4, "2Y"),
                (5, "3A"),
                (6, "3Y"),
                (7, "Ground"),
                (8, "6A"),
                (9, "6Y"),
                (10, "5A"),
                (11, "5Y"),
                (12, "4A"),
                (13, "VCC"),
                (14, "4Y"),
            ],
        )

    def test_extracts_timer_top_view_when_pin_table_uses_full_names(self):
        chunks = [
            """R
R
R
GND
TRIGGER
OUTPUT
RESET
+VCC
DISCHARGE
THRESHOLD
CONTROL
VOLTAGE
COMPARATOR
COMPARATOR""",
            """D, P, and DGK Packages
8-Pin PDIP, SOIC, and VSSOP
Top View
Pin Functions
PIN
I/O""",
            """NO.
NAME
Control
Voltage
I
Controls the threshold and trigger levels.
Discharge
I
Open collector output which discharges a capacitor between intervals.
GND
O
Ground reference voltage
Output
O
Output driven waveform
Reset
I
Negative pulse applied to this pin to disable or reset the timer.
Threshold
I
Compares the voltage applied to the terminal.
Trigger
I
Responsible for transition of the flip-flop.
V+
I
Supply voltage with respect to GND""",
        ]
        metadata = [
            {"source": "lm555.pdf", "page": 3},
            {"source": "lm555.pdf", "page": 3},
            {"source": "lm555.pdf", "page": 3},
        ]

        pinout = extract_pinout_map(chunks, metadata, "lm555.pdf")

        self.assertEqual(
            [(pin["pin"], pin["function"]) for pin in pinout["pins"]],
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


if __name__ == "__main__":
    unittest.main()
