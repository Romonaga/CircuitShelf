from __future__ import annotations

import re
from collections import OrderedDict
from typing import Any

from db.lab_inventory import normalize_part_name


QUANTITY_RE = re.compile(
    r"\b(?:about|around|approx(?:imately)?|~)?\s*(?:x\s*)?(\d{1,5})\s*(?:x|pcs?|pieces?|count|qty|of each)?\b",
    re.IGNORECASE,
)
MODEL_RE = re.compile(r"\b[A-Za-z]{1,8}\d{2,5}[A-Za-z0-9-]*\b")


def parse_inventory_import(text: str, existing_parts: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    existing_index = {
        normalize_part_name(part.get("displayName") or ""): part
        for part in existing_parts or []
    }
    existing_index.update(
        {
            normalize_part_name(alias): part
            for part in existing_parts or []
            for alias in part.get("aliases") or []
        }
    )

    items = []
    for raw_line in inventory_lines(text):
        for item in parse_line(raw_line):
            normalized = normalize_part_name(item["displayName"])
            existing = existing_index.get(normalized)
            if not existing:
                for alias in item.get("aliases") or []:
                    existing = existing_index.get(normalize_part_name(alias))
                    if existing:
                        break
            item["normalizedName"] = normalized
            item["action"] = "merge" if existing else "create"
            item["existingPartId"] = existing.get("id") if existing else None
            items.append(item)

    items = dedupe_import_items(items)
    return {
        "items": items,
        "count": len(items),
    }


def inventory_lines(text: str) -> list[str]:
    cleaned = str(text or "").replace("\r", "\n")
    raw_lines = []
    for line in cleaned.split("\n"):
        for part in re.split(r";", line):
            item = re.sub(r"^\s*[-*•]\s*", "", part).strip()
            if item:
                raw_lines.append(item)
    return raw_lines


def parse_line(raw_line: str) -> list[dict[str, Any]]:
    line = raw_line.strip()
    if not line:
        return []

    quantity = extract_quantity(line)
    lowered = line.lower()
    models = [model.upper() for model in MODEL_RE.findall(line)]
    if "of each" in lowered and len(models) > 1:
        return [part_from_text(model, quantity, raw_line) for model in models]
    return [part_from_text(line, quantity, raw_line)]


def extract_quantity(line: str) -> int:
    lowered = line.lower()
    if any(word in lowered for word in ("tons", "hundreds", "100s", "100;s")):
        return 100
    if any(word in lowered for word in ("bunch", "collection", "assortment", "many", "lots")):
        return 1
    match = QUANTITY_RE.search(line)
    if match:
        return max(1, int(match.group(1)))
    return 1


def part_from_text(text: str, quantity: int, raw_line: str) -> dict[str, Any]:
    lower = text.lower()
    warnings: list[str] = []

    if "resistor" in lower:
        return import_item("Assorted resistors", "resistor", quantity, raw_line, resistor_aliases(), "Resistor assortment. Verify power rating, tolerance, and voltage rating before use.", warnings)
    if "capacitor" in lower or "cap " in f"{lower} " or "caps" in lower:
        return import_item("Assorted capacitors", "capacitor", quantity, raw_line, capacitor_aliases(), "Capacitor assortment. Verify voltage rating, polarity, ESR, and tolerance before use.", warnings)
    if "diode" in lower:
        return import_item("Assorted diodes", "diode", quantity, raw_line, diode_aliases(), "Diode assortment. Verify current, reverse voltage, speed, and polarity before use.", warnings)
    if "led" in lower or "light emitting diode" in lower:
        color = led_color(lower)
        display_name = f"{color.title()} LEDs" if color else "Assorted LEDs"
        aliases = ["led", "leds", "light emitting diode", f"{color} led" if color else ""]
        notes = "LED inventory. Verify forward voltage, current limit resistor, package size, and polarity before use."
        return import_item(display_name, "diode", quantity, raw_line, aliases, notes, warnings)
    if "raspberry" in lower or "raspi" in lower or re.search(r"\brpi\b|\bpi\s*[45]\b", lower):
        return import_item("Raspberry Pi boards", "board", quantity, raw_line, ["raspberry pi", "raspi", "rpi", "raspberry pi 4", "pi 4", "raspberry pi 5", "pi 5", "gpio board", "sbc", "3.3v gpio"], "Raspberry Pi boards. GPIO is 3.3 V logic only.", warnings)
    if "arduino" in lower and any(word in lower for word in ("bare", "ic", "chip")):
        warnings.append("Assumed base Arduino bare IC is ATmega328P/Arduino Uno class; confirm the marking and bootloader.")
        return import_item("ATmega328P bare Arduino ICs", "ic", quantity, raw_line, ["atmega328p", "atmega328", "arduino bare ic", "arduino uno chip", "arduino bootloader chip", "avr microcontroller", "base arduino ic"], "Bare Arduino-compatible microcontrollers. Verify package, clock, and bootloader.", warnings)
    if "arduino" in lower:
        return import_item("Arduino-compatible boards", "board", quantity, raw_line, ["arduino", "arduino uno", "arduino nano", "microcontroller board", "5v arduino"], "Arduino-compatible development boards.", warnings)
    if re.search(r"\b(?:lm|ne)?555\b", lower) or re.search(r"\b(?:lm|ne)?556\b", lower):
        return import_item("LM555 and LM556 timer ICs", "ic", quantity, raw_line, ["lm555", "ne555", "555", "555 timer", "lm556", "ne556", "556 timer", "dual 555 timer", "astable timer", "monostable timer"], "555/556 timer IC collection. Verify exact package and supply-voltage range.", warnings)
    if "logic" in lower or re.search(r"\b(?:74hc|74ls|74xx|cd4000|4000 series)\b", lower):
        return import_item("Assorted logic ICs", "ic", quantity, raw_line, ["logic chip", "logic ic", "digital logic", "ttl logic", "cmos logic", "74xx", "74hc", "74ls", "4000 series", "and gate", "or gate", "not gate", "nand gate", "flip flop", "counter ic", "shift register"], "Digital logic IC collection. Verify family, voltage range, package, and pinout.", warnings)
    if "segment" in lower and "led" in lower:
        return import_item("Assorted seven-segment LED displays", "display", quantity, raw_line, ["seven segment display", "7 segment display", "7-segment display", "segment led", "led digit display", "common anode display", "common cathode display"], "Seven-segment LED display collection. Verify common-anode/common-cathode wiring.", warnings)
    if re.search(r"\b128\s*x?\s*32\b", lower) or ("oled" in lower and "display" in lower):
        return import_item("128x32 LED/OLED display modules", "display", quantity, raw_line, ["128x32 display", "128 32 display", "128x32 oled", "oled display", "led screen", "i2c display", "spi display", "ssd1306"], "128x32 display modules. Verify interface, voltage, and controller IC.", warnings)

    model = first_model(text)
    if model:
        if model in {"BMP250", "BMP150"}:
            warnings.append(f"{model} is less common in hobby modules than BMP180/BMP280/BME280; confirm the part marking.")
        return import_item(f"{model} modules", infer_model_type(model), quantity, raw_line, aliases_for_model(model), f"Imported from free-form inventory line: {raw_line}", warnings)

    warnings.append("Low-confidence import; review name, type, aliases, and quantity before approval.")
    return import_item(clean_display_name(text), "component", quantity, raw_line, [clean_display_name(text)], f"Imported from free-form inventory line: {raw_line}", warnings, confidence=0.45)


def import_item(display_name: str, part_type: str, quantity: int, raw_line: str, aliases: list[str], notes: str, warnings: list[str], confidence: float = 0.86) -> dict[str, Any]:
    if quantity == 1 and re.search(r"\b(bunch|collection|assortment|many|lots|good collection)\b", raw_line, re.IGNORECASE):
        warnings = [*warnings, "Quantity treated as a collection marker because the line did not include an exact count."]
    return {
        "rawLine": raw_line,
        "displayName": display_name,
        "partType": part_type,
        "quantity": max(1, int(quantity or 1)),
        "location": "",
        "notes": notes,
        "aliases": dedupe_strings(aliases),
        "confidence": confidence if not warnings else min(confidence, 0.72),
        "warnings": dedupe_strings(warnings),
    }


def first_model(text: str) -> str:
    matches = MODEL_RE.findall(text)
    return matches[0].upper() if matches else ""


def infer_model_type(model: str) -> str:
    if model.startswith(("BMP", "BME", "DHT", "DS18", "MPU")):
        return "sensor"
    if model.startswith(("ATMEGA", "ATTINY", "PIC")):
        return "ic"
    if model.startswith(("LM", "NE", "TL", "CD", "74")):
        return "ic"
    return "module"


def aliases_for_model(model: str) -> list[str]:
    aliases = [model, model.lower()]
    if model.startswith("BMP"):
        aliases.extend(["pressure sensor", "barometric pressure sensor", "barometer sensor", "i2c pressure sensor"])
    if model.startswith("ADS"):
        aliases.extend(["adc", "analog to digital converter", "i2c adc"])
    return aliases


def clean_display_name(value: str) -> str:
    text = re.sub(r"\b(?:have|i have|about|around|approx(?:imately)?|x?\s*\d+\s*x?)\b", " ", value, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip(" ,.-")
    return text[:80] or "Imported part"


def led_color(text: str) -> str:
    for color in ("white", "yellow", "blue", "red", "green", "orange", "amber", "rgb"):
        if re.search(rf"\b{color}\b", text, re.IGNORECASE):
            return color
    return ""


def resistor_aliases() -> list[str]:
    return ["resistor", "resistors", "through-hole resistor", "assorted resistor values", "10 ohm resistor", "100 ohm resistor", "220 ohm resistor", "330 ohm resistor", "470 ohm resistor", "1 kohm resistor", "10 kohm resistor", "100 kohm resistor"]


def capacitor_aliases() -> list[str]:
    return ["capacitor", "capacitors", "ceramic capacitor", "electrolytic capacitor", "film capacitor", "metallized film capacitor", "decoupling capacitor", "bypass capacitor", "0.1 uf capacitor", "100 nf capacitor", "10 uf capacitor", "timing capacitor"]


def diode_aliases() -> list[str]:
    return ["diode", "diodes", "rectifier diode", "signal diode", "switching diode", "zener diode", "schottky diode", "flyback diode", "1n4148", "1n4007"]


def dedupe_import_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for item in items:
        key = normalize_part_name(item["displayName"])
        existing = result.get(key)
        if not existing:
            result[key] = item
            continue
        existing["quantity"] = max(int(existing["quantity"]), int(item["quantity"]))
        existing["aliases"] = dedupe_strings([*existing.get("aliases", []), *item.get("aliases", [])])
        existing["warnings"] = dedupe_strings([*existing.get("warnings", []), *item.get("warnings", [])])
        existing["rawLine"] = f"{existing['rawLine']} | {item['rawLine']}"
    return list(result.values())


def dedupe_strings(items: list[str]) -> list[str]:
    result = OrderedDict()
    for item in items:
        text = str(item or "").strip()
        if text:
            result.setdefault(text.lower(), text)
    return list(result.values())
