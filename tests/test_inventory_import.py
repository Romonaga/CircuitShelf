import unittest

from inventory_import import parse_inventory_import


class InventoryImportTests(unittest.TestCase):
    def test_parses_timer_and_assorted_passives(self):
        result = parse_inventory_import("20x NE555\nbunch of 10k resistors")
        items = {item["displayName"]: item for item in result["items"]}

        self.assertEqual(items["LM555 and LM556 timer ICs"]["quantity"], 20)
        self.assertEqual(items["LM555 and LM556 timer ICs"]["partType"], "ic")
        self.assertIn("ne555", items["LM555 and LM556 timer ICs"]["aliases"])
        self.assertEqual(items["Assorted resistors"]["partType"], "resistor")
        self.assertTrue(items["Assorted resistors"]["warnings"])

    def test_of_each_creates_one_part_per_model(self):
        result = parse_inventory_import("about 15 BMP150 BMP250 of each")
        items = {item["displayName"]: item for item in result["items"]}

        self.assertEqual(items["BMP150 modules"]["quantity"], 15)
        self.assertEqual(items["BMP250 modules"]["quantity"], 15)
        self.assertEqual(items["BMP150 modules"]["partType"], "sensor")
        self.assertTrue(items["BMP250 modules"]["warnings"])

    def test_preview_marks_existing_alias_matches_as_merge(self):
        existing = [
            {
                "id": "part-1",
                "displayName": "Resistor collection",
                "aliases": ["resistor", "10 kohm resistor"],
            }
        ]

        result = parse_inventory_import("bunch of 10k resistors", existing)

        self.assertEqual(result["items"][0]["action"], "merge")
        self.assertEqual(result["items"][0]["existingPartId"], "part-1")

    def test_led_color_lines_with_trailing_x_quantity(self):
        result = parse_inventory_import("White LED X50\nYellow LED X50\nBlue LED X50")
        items = {item["displayName"]: item for item in result["items"]}

        self.assertEqual(items["White LEDs"]["quantity"], 50)
        self.assertEqual(items["White LEDs"]["partType"], "diode")
        self.assertIn("white led", items["White LEDs"]["aliases"])
        self.assertEqual(items["Yellow LEDs"]["quantity"], 50)
        self.assertEqual(items["Blue LEDs"]["quantity"], 50)


if __name__ == "__main__":
    unittest.main()
