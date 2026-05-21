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
        self.assertEqual(pinout["pins"][1]["function"], "GND")


if __name__ == "__main__":
    unittest.main()
