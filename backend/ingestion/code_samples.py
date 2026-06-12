from __future__ import annotations

import os
import re
from collections import OrderedDict
from pathlib import PurePosixPath
from typing import Any


CODE_SAMPLE_SOURCE_EXTENSIONS = {
    ".ino",
    ".c",
    ".cc",
    ".cpp",
    ".cxx",
    ".h",
    ".hh",
    ".hpp",
    ".go",
    ".js",
    ".jsx",
    ".py",
    ".rs",
    ".sh",
    ".ts",
    ".tsx",
}

CODE_SAMPLE_COMPANION_EXTENSIONS = {
    ".ini",
    ".json",
    ".md",
    ".mod",
    ".properties",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}

CODE_SAMPLE_EXTENSIONS = CODE_SAMPLE_SOURCE_EXTENSIONS | CODE_SAMPLE_COMPANION_EXTENSIONS

UPLOAD_CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f]")
MAX_UPLOAD_PATH_PART_LENGTH = 180
IGNORED_UPLOAD_PATH_PARTS = {
    ".bzr",
    ".cache",
    ".git",
    ".hg",
    ".idea",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".svn",
    ".venv",
    ".vscode",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "target",
    "venv",
}

IGNORED_CODE_BUNDLE_PATH_PARTS = {
    "debug",
    "ewarm",
    "iar",
    "mdk-arm",
    "release",
    "rte",
}

IGNORED_CODE_BUNDLE_PATH_PART_RE = re.compile(
    r"(?:^cmsis$|(?:^|[_-])hal[_-]?driver$)",
    re.IGNORECASE,
)

LANGUAGE_BY_EXTENSION = {
    ".ino": "Arduino",
    ".c": "C",
    ".cc": "C++",
    ".cpp": "C++",
    ".cxx": "C++",
    ".h": "C/C++ header",
    ".hh": "C++ header",
    ".hpp": "C++ header",
    ".go": "Go",
    ".js": "JavaScript",
    ".jsx": "React JSX",
    ".py": "Python",
    ".rs": "Rust",
    ".sh": "Shell",
    ".ts": "TypeScript",
    ".tsx": "React TSX",
    ".ini": "configuration",
    ".json": "manifest",
    ".md": "Markdown",
    ".properties": "properties",
    ".toml": "configuration",
    ".txt": "text",
    ".yaml": "configuration",
    ".yml": "configuration",
}

INTERFACE_PATTERNS = {
    "I2C": re.compile(r"\b(?:i2c|wire\.begin|sda|scl)\b", re.IGNORECASE),
    "SPI": re.compile(r"\b(?:spi|mosi|miso|sck|ss|cs)\b", re.IGNORECASE),
    "UART": re.compile(r"\b(?:uart|serial(?:\d+)?\.begin|tx|rx)\b", re.IGNORECASE),
    "PWM": re.compile(r"\b(?:pwm|analogwrite)\b", re.IGNORECASE),
    "ADC": re.compile(r"\b(?:adc|analogread|analog input)\b", re.IGNORECASE),
    "GPIO": re.compile(r"\b(?:gpio|pinmode|digitalwrite|digitalread)\b", re.IGNORECASE),
    "WebSerial": re.compile(r"\b(?:webserial|serialport|navigator\.serial)\b", re.IGNORECASE),
    "WebUSB": re.compile(r"\b(?:webusb|navigator\.usb)\b", re.IGNORECASE),
}

BOARD_PATTERNS = (
    ("ESP32", re.compile(r"\besp32\b", re.IGNORECASE)),
    ("Arduino", re.compile(r"\b(?:arduino|uno|nano|mega|leonardo)\b", re.IGNORECASE)),
    ("Raspberry Pi Pico", re.compile(r"\b(?:rp2040|pico)\b", re.IGNORECASE)),
    ("Raspberry Pi", re.compile(r"\braspberry\s*pi\b", re.IGNORECASE)),
)

CODE_COMPANION_MARKER_RE = re.compile(
    r"\b(?:setup|loop|pinmode|digitalwrite|analogread|serial\.begin|baud|AT\+[A-Z0-9_]+|#include|import\s+board|machine\.Pin|machine\.GPIO|gpio|i2c|spi|uart|arduino|esp32|raspberry\s*pi|circuitpython|micropython|platformio|tinygo|embedded-hal|react|serialport|webserial|webusb|navigator\.serial|navigator\.usb)\b",
    re.IGNORECASE,
)
KNOWN_CODE_COMPANION_FILES = {
    "cargo.toml",
    "go.mod",
    "library.json",
    "library.properties",
    "package.json",
    "platformio.ini",
    "pyproject.toml",
    "readme.md",
    "requirements.txt",
}

FRAMEWORK_PATTERNS = (
    ("Arduino", re.compile(r"\bsetup\s*\(\s*\)|\bloop\s*\(\s*\)|#include\s*<Arduino\.h>", re.IGNORECASE)),
    ("CircuitPython", re.compile(r"\b(?:import\s+board|import\s+digitalio|adafruit_)", re.IGNORECASE)),
    ("MicroPython", re.compile(r"\bfrom\s+machine\s+import\b|\bmachine\.Pin\b", re.IGNORECASE)),
    ("TinyGo", re.compile(r"\b(?:tinygo|machine\.GPIO|machine\.Pin|machine\.UART|machine\.I2C|machine\.SPI)\b", re.IGNORECASE)),
    ("Rust embedded", re.compile(r"\b(?:embedded[_-]hal|esp[_-]idf|rp2040[_-]hal|arduino[_-]hal)\b", re.IGNORECASE)),
    ("React", re.compile(r"\b(?:react|jsx|tsx|useState|useEffect|createRoot|navigator\.serial|navigator\.usb)\b", re.IGNORECASE)),
)

COMPONENT_PATTERNS = (
    ("LED", re.compile(r"\bled\b|neopixel|ws2812", re.IGNORECASE)),
    ("servo", re.compile(r"\bservo\b", re.IGNORECASE)),
    ("relay", re.compile(r"\brelay\b", re.IGNORECASE)),
    ("button", re.compile(r"\bbutton\b|pushbutton|switch", re.IGNORECASE)),
    ("DHT sensor", re.compile(r"\bdht(?:11|22)?\b", re.IGNORECASE)),
    ("BME280 sensor", re.compile(r"\bbme280\b", re.IGNORECASE)),
    ("BMP280 sensor", re.compile(r"\bbmp280\b", re.IGNORECASE)),
    ("SSD1306 display", re.compile(r"\bssd1306\b|oled", re.IGNORECASE)),
    ("ADS1115 ADC", re.compile(r"\bads1115\b", re.IGNORECASE)),
    ("HC-SR04 ultrasonic sensor", re.compile(r"\bhc[-_ ]?sr04\b|ultrasonic", re.IGNORECASE)),
    ("serial device", re.compile(r"\b(?:webserial|serialport|navigator\.serial)\b", re.IGNORECASE)),
    ("USB device", re.compile(r"\b(?:webusb|navigator\.usb)\b", re.IGNORECASE)),
)


def is_code_sample_path(path: str) -> bool:
    return os.path.splitext(str(path or ""))[1].lower() in CODE_SAMPLE_SOURCE_EXTENSIONS


def is_code_sample_companion_path(path: str, text: str) -> bool:
    value = str(path or "").replace("\\", "/")
    ext = os.path.splitext(value)[1].lower()
    if ext not in CODE_SAMPLE_COMPANION_EXTENSIONS:
        return False
    name = os.path.basename(value).lower()
    if name not in KNOWN_CODE_COMPANION_FILES and name not in {"readme.txt"}:
        return False
    return bool(CODE_COMPANION_MARKER_RE.search(text or ""))


def safe_relative_upload_path(filename: str, supported_extensions: set[str]) -> str:
    raw = str(filename or "").replace("\\", "/").strip()
    if raw.startswith("/"):
        raise ValueError("Upload file name is not allowed.")
    parts = [part.strip() for part in raw.split("/") if part.strip()]
    if not parts:
        raise ValueError("Upload must include a file name.")
    if any(part in {".", ".."} or part.startswith(".") for part in parts):
        raise ValueError("Upload file name is not allowed.")
    safe_parts = []
    for part in parts:
        if (
            len(part) > MAX_UPLOAD_PATH_PART_LENGTH
            or UPLOAD_CONTROL_CHAR_RE.search(part)
            or "/" in part
            or "\\" in part
        ):
            raise ValueError("Upload file name is not allowed.")
        safe_parts.append(part)
    ext = os.path.splitext(safe_parts[-1])[1].lower()
    if ext not in supported_extensions:
        allowed = ", ".join(sorted(supported_extensions))
        raise ValueError(f"Unsupported file type. Allowed: {allowed}")
    return "/".join(safe_parts)


def is_ignored_upload_path(filename: str) -> bool:
    raw = str(filename or "").replace("\\", "/").strip()
    parts = [part.strip() for part in raw.split("/") if part.strip()]
    for part in parts:
        lowered = part.lower()
        if lowered in {".", ".."}:
            return False
        if lowered in IGNORED_UPLOAD_PATH_PARTS or lowered.startswith("."):
            return True
    return False


def is_ignored_code_bundle_dependency_path(filename: str) -> bool:
    raw = str(filename or "").replace("\\", "/").strip()
    parts = [part.strip() for part in raw.split("/") if part.strip()]
    for part in parts:
        lowered = part.lower()
        if lowered in IGNORED_CODE_BUNDLE_PATH_PARTS:
            return True
        if IGNORED_CODE_BUNDLE_PATH_PART_RE.search(part):
            return True
    return False


def code_sample_metadata(path: str, text: str) -> dict[str, Any]:
    rel_path = str(path or "").replace("\\", "/")
    posix = PurePosixPath(rel_path)
    parts = [part for part in posix.parts if part not in {"", ".", posix.anchor, "/"}]
    if posix.is_absolute():
        pack_key = parts[-2] if len(parts) > 1 else posix.stem
    else:
        pack_key = parts[0] if len(parts) > 1 else posix.stem
    language = LANGUAGE_BY_EXTENSION.get(posix.suffix.lower(), posix.suffix.lower().lstrip(".") or "code")
    haystack = f"{rel_path}\n{text or ''}"
    libraries = extract_libraries(text)
    pins = extract_pin_assignments(text)
    at_commands = extract_at_commands(text)
    serial_settings = extract_serial_settings(text)
    metadata = {
        "code_sample": True,
        "code_pack": pack_key,
        "code_pack_display": display_name(pack_key),
        "code_file": rel_path,
        "code_language": language,
        "code_role": code_role(rel_path),
        "code_framework": first_match(FRAMEWORK_PATTERNS, haystack),
        "code_board": first_match(BOARD_PATTERNS, haystack),
        "code_libraries": libraries,
        "code_components": extract_components(haystack, libraries),
        "code_interfaces": extract_interfaces(haystack),
        "code_pins": pins,
        "code_at_commands": at_commands,
        "code_serial_settings": serial_settings,
    }
    metadata["code_summary"] = code_summary(metadata)
    return metadata


def annotated_code_text(path: str, text: str, metadata: dict[str, Any] | None = None) -> str:
    metadata = metadata or code_sample_metadata(path, text)
    lines = [
        f"Code sample pack: {metadata.get('code_pack_display') or metadata.get('code_pack')}",
        f"Code file: {metadata.get('code_file') or path}",
        f"Language: {metadata.get('code_language') or 'code'}",
    ]
    for label, key in (
        ("Framework", "code_framework"),
        ("Board", "code_board"),
        ("Libraries", "code_libraries"),
        ("Components", "code_components"),
        ("Interfaces", "code_interfaces"),
        ("AT commands", "code_at_commands"),
        ("Serial", "code_serial_settings"),
    ):
        value = metadata.get(key)
        if isinstance(value, list):
            value = ", ".join(str(item) for item in value if item)
        if value:
            lines.append(f"{label}: {value}")
    pins = metadata.get("code_pins") or []
    if pins:
        pin_text = ", ".join(f"{item['name']}={item['pin']}" for item in pins[:12])
        lines.append(f"Pins: {pin_text}")
    lines.extend(["", "Source code:", text or ""])
    return "\n".join(lines).strip()


def extract_libraries(text: str) -> list[str]:
    result: OrderedDict[str, str] = OrderedDict()
    for match in re.finditer(r"#include\s*[<\"]([^>\"]+)[>\"]", text or ""):
        name = os.path.splitext(os.path.basename(match.group(1).strip()))[0]
        if name:
            result.setdefault(name.lower(), name)
    for match in re.finditer(r"^\s*(?:from|import)\s+([A-Za-z_][A-Za-z0-9_\.]*)", text or "", re.MULTILINE):
        name = match.group(1).split(".")[0]
        if name:
            result.setdefault(name.lower(), name)
    for match in re.finditer(r"^\s*import\s+(?:\([\s\S]*?\)|\"[^\"]+\")", text or "", re.MULTILINE):
        block = match.group(0)
        for package in re.findall(r"\"([^\"]+)\"", block):
            name = package.split("/")[-1] or package
            if name:
                result.setdefault(name.lower(), name)
    for match in re.finditer(r"^\s*(?:use|extern\s+crate)\s+([A-Za-z_][A-Za-z0-9_:]*)", text or "", re.MULTILINE):
        name = match.group(1).split("::")[0]
        if name:
            result.setdefault(name.lower(), name)
    for match in re.finditer(r"(?:import\s+(?:[^;]*?\s+from\s+)?|require\s*\()\s*[\"']([^\"']+)[\"']", text or ""):
        name = match.group(1).split("/")[-1] or match.group(1)
        if name:
            result.setdefault(name.lower(), name)
    return list(result.values())[:24]


def extract_interfaces(text: str) -> list[str]:
    return [name for name, pattern in INTERFACE_PATTERNS.items() if pattern.search(text or "")]


def extract_components(text: str, libraries: list[str] | None = None) -> list[str]:
    result: OrderedDict[str, str] = OrderedDict()
    for name, pattern in COMPONENT_PATTERNS:
        if pattern.search(text or ""):
            result.setdefault(name.lower(), name)
    for library in libraries or []:
        normalized = library.replace("_", " ").replace("-", " ")
        for name, pattern in COMPONENT_PATTERNS:
            if pattern.search(normalized):
                result.setdefault(name.lower(), name)
    return list(result.values())[:24]


def extract_pin_assignments(text: str) -> list[dict[str, str]]:
    result: OrderedDict[str, dict[str, str]] = OrderedDict()
    patterns = (
        re.compile(r"\b(?:const\s+)?(?:int|byte|uint8_t|#define)\s+([A-Za-z_][A-Za-z0-9_]*)\s*(?:=|\s)\s*([A-Za-z]?\d{1,3})\b"),
        re.compile(r"\b(?:const|let|var)\s+([A-Za-z_][A-Za-z0-9_]*pin[A-Za-z0-9_]*)\s*(?::\s*[A-Za-z0-9_<>\[\]]+)?\s*=\s*([A-Za-z]?\d{1,3})\b", re.IGNORECASE),
        re.compile(r"\bconst\s+([A-Za-z_][A-Za-z0-9_]*pin[A-Za-z0-9_]*)\s+[A-Za-z0-9_]+\s*=\s*([A-Za-z]?\d{1,3})\b", re.IGNORECASE),
        re.compile(r"\b(?:let|const)\s+([A-Za-z_][A-Za-z0-9_]*pin[A-Za-z0-9_]*)\s*:\s*[A-Za-z0-9_:<>]+\s*=\s*([A-Za-z]?\d{1,3})\b", re.IGNORECASE),
        re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*Pin)\s*=\s*([A-Za-z]?\d{1,3})\b", re.IGNORECASE),
        re.compile(r"\b(?:Pin|GPIO|gpio\.NewPin|Pin::new)\s*\(\s*([A-Za-z]?\d{1,3})\s*\)", re.IGNORECASE),
        re.compile(r"\bmachine\.GPIO(\d{1,3})\b", re.IGNORECASE),
    )
    for pattern in patterns:
        for match in pattern.finditer(text or ""):
            if len(match.groups()) == 1:
                name, pin = "pin", match.group(1)
            else:
                name, pin = match.group(1), match.group(2)
            key = f"{name.lower()}:{pin}"
            result.setdefault(key, {"name": name, "pin": pin})
    return list(result.values())[:32]


def extract_at_commands(text: str) -> list[str]:
    result: OrderedDict[str, str] = OrderedDict()
    for match in re.finditer(r"\bAT\+[A-Z0-9_]+(?:=[A-Z0-9_,\".\-:/ ]{0,80})?", text or "", re.IGNORECASE):
        command = match.group(0).strip().rstrip("\"'.,;")
        result.setdefault(command.upper(), command)
    return list(result.values())[:32]


def extract_serial_settings(text: str) -> list[str]:
    result: OrderedDict[str, str] = OrderedDict()
    for match in re.finditer(r"\bSerial(?:\d+)?\.begin\s*\(\s*(\d{4,7})", text or "", re.IGNORECASE):
        baud = match.group(1)
        result.setdefault(f"serial:{baud}", f"Serial baud {baud}")
    for match in re.finditer(r"\bbaud(?:\s*rate)?\s*[:=]\s*(\d{4,7})", text or "", re.IGNORECASE):
        baud = match.group(1)
        result.setdefault(f"baud:{baud}", f"Baud {baud}")
    return list(result.values())[:16]


def first_match(patterns: tuple[tuple[str, re.Pattern[str]], ...], text: str) -> str:
    for label, pattern in patterns:
        if pattern.search(text or ""):
            return label
    return ""


def code_role(path: str) -> str:
    name = os.path.basename(path).lower()
    if name.endswith((".h", ".hh", ".hpp")):
        return "header"
    if name in {"main.cpp", "main.c", "main.go", "main.py", "main.rs", "app.jsx", "app.tsx"} or name.endswith(".ino"):
        return "entrypoint"
    if "test" in name:
        return "test"
    return "source"


def display_name(value: str) -> str:
    text = re.sub(r"[_-]+", " ", str(value or "")).strip()
    return text[:1].upper() + text[1:] if text else "Code sample"


def code_summary(metadata: dict[str, Any]) -> str:
    bits = [metadata.get("code_pack_display") or metadata.get("code_pack") or "Code sample"]
    if metadata.get("code_board"):
        bits.append(f"for {metadata['code_board']}")
    if metadata.get("code_framework"):
        bits.append(f"using {metadata['code_framework']}")
    components = metadata.get("code_components") or []
    if components:
        bits.append("with " + ", ".join(components[:4]))
    interfaces = metadata.get("code_interfaces") or []
    if interfaces:
        bits.append("over " + ", ".join(interfaces[:4]))
    return " ".join(str(bit) for bit in bits if bit)
