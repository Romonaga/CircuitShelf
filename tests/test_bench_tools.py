import unittest
from io import BytesIO

from PIL import Image

from backend.services.bench_tools import analyze_bench_photo, build_assembly_export


class BenchToolsTests(unittest.TestCase):
    def test_analyzes_bench_photo(self):
        image = Image.new("RGB", (800, 600), "white")
        out = BytesIO()
        image.save(out, format="PNG")

        diagnostics = analyze_bench_photo(out.getvalue())

        self.assertEqual(diagnostics["width"], 800)
        self.assertEqual(diagnostics["height"], 600)
        self.assertIn("brightness", diagnostics)
        self.assertIn("dominantColors", diagnostics)

    def test_555_plan_exports_real_spice_starter(self):
        plan = {
            "title": "NE555 build card",
            "objective": "Build a 555 timer LED flasher",
            "componentName": "NE555",
            "componentType": "timer",
            "parts": [{"name": "Timing resistor", "detail": "10 kOhm"}],
            "power": [],
            "steps": [
                {"ordinal": 1, "title": "Pin 1 GND", "instruction": "Ground rail", "note": ""},
                {"ordinal": 2, "title": "Pin 3 OUT", "instruction": "LED plus resistor", "note": ""},
            ],
            "sources": [],
        }

        exported = build_assembly_export(plan, "ltspice")

        self.assertEqual(exported["filename"], "NE555-build-card.cir")
        self.assertIn("XU1", exported["content"])
        self.assertIn("NE555", exported["content"])


if __name__ == "__main__":
    unittest.main()
