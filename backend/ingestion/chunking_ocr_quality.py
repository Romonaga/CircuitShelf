import re

import numpy as np


class OcrQualityMixin:
    def clean_ocr_text(self, text: str) -> str:
        """Normalize OCR text before scoring or indexing."""
        return re.sub(r"\s+", " ", self.normalize_extracted_text(str(text or ""))).strip()

    @staticmethod
    def has_ocr_value_signal(text: str) -> bool:
        """Return true when short OCR text still looks useful for electronics retrieval."""
        lower = text.lower()
        electronics_terms = [
            "breadboard", "component", "connection", "resistor", "capacitor", "transistor",
            "diode", "led", "switch", "jumper", "battery", "ground", "timer", "trigger",
            "threshold", "discharge", "reset", "output", "input", "vcc", "gnd", "pin",
            "ohm", "kohm", "uf", "pf", "nf", "volt", "voltage", "current", "frequency",
            "duty", "monostable", "astable", "experiment", "chapter", "schematic",
        ]
        if any(term in lower for term in electronics_terms):
            return True
        if re.search(r"\b[A-Z]{1,6}\d*\([A-Z+\-]+\)\s*=>\s*[A-Z]\d+\b", text):
            return True
        if re.search(r"\b\d+(\.\d+)?\s*(k?ohm|kq|q|uf|µf|pf|nf|v|ma)\b", lower):
            return True
        return False

    def is_isolated_ocr_noise(self, text: str) -> bool:
        stripped = text.strip()
        if not stripped:
            return True
        if self.is_low_value_line(stripped):
            return True
        if re.fullmatch(r"[\W\d_]+", stripped):
            return True
        if re.fullmatch(r"(?:page|fig(?:ure)?|table)?\s*\d+[A-Za-z]?", stripped, re.IGNORECASE):
            return True
        if re.fullmatch(r"\d{1,2}[-/][A-Za-z]{3}[-/]\d{2,4}", stripped):
            return True
        return False

    def evaluate_ocr_quality(self, text, ocr_confidence=None):
        text = self.clean_ocr_text(text)
        if not text:
            return 0.0, "Empty"

        unique_chars = len(set(text))
        words = text.split()
        meaningful_words = re.findall(r"[A-Za-z]{2,}", text)
        avg_word_len = np.mean([len(w) for w in words]) if words else 0
        alpha_ratio = sum(c.isalpha() for c in text) / len(text)
        digit_ratio = sum(c.isdigit() for c in text) / len(text)
        space_ratio = sum(c.isspace() for c in text) / len(text)
        symbol_ratio = sum(not c.isalnum() and not c.isspace() for c in text) / len(text)
        has_value_signal = self.has_ocr_value_signal(text)

        min_length = self.config.get("OCR_MIN_LENGTH", 20)
        min_meaningful_chars = self.config.get("OCR_MIN_MEANINGFUL_CHARS", 80)
        min_meaningful_words = self.config.get("OCR_MIN_MEANINGFUL_WORDS", 6)
        short_text_max_score = self.config.get("OCR_SHORT_TEXT_MAX_SCORE", 0.3)
        low_content_max_score = self.config.get("OCR_LOW_CONTENT_MAX_SCORE", 0.2)
        min_unique_chars = self.config.get("OCR_MIN_UNIQUE_CHARS", 10)
        max_avg_word_len = self.config.get("OCR_MAX_AVG_WORD_LEN", 12)
        min_alpha_ratio = self.config.get("OCR_MIN_ALPHA_RATIO", 0.3)
        max_symbol_ratio = self.config.get("OCR_MAX_SYMBOL_RATIO", 0.4)
        max_digit_ratio = self.config.get("OCR_MAX_DIGIT_RATIO", 0.5)
        max_space_ratio = self.config.get("OCR_MAX_SPACE_RATIO", 0.3)
        min_confidence = self.config.get("OCR_MIN_CONFIDENCE", 25)

        score = 1.0
        details = []

        if self.is_isolated_ocr_noise(text):
            return 0.0, "isolated OCR noise"

        if len(text) < min_length:
            score -= 0.4
            details.append("too short")

        if len(text) < min_meaningful_chars and not has_value_signal:
            score = min(score, short_text_max_score)
            details.append("short text without electronics signal")

        if len(meaningful_words) < min_meaningful_words and not has_value_signal:
            score = min(score, low_content_max_score)
            details.append("low meaningful word count")

        if unique_chars < min_unique_chars:
            score -= 0.3
            details.append("low uniqueness")

        if avg_word_len > max_avg_word_len:
            score -= 0.2
            details.append("long words")

        if alpha_ratio < min_alpha_ratio:
            score -= 0.2
            details.append("low alphabetic ratio")

        if symbol_ratio > max_symbol_ratio:
            score -= 0.2
            details.append("too many symbols")

        if digit_ratio > max_digit_ratio:
            score -= 0.2
            details.append("too many digits")

        if space_ratio > max_space_ratio:
            score -= 0.2
            details.append("too much whitespace")

        if ocr_confidence is not None and ocr_confidence < min_confidence:
            score -= 0.3
            details.append(f"low tesseract confidence ({ocr_confidence:.1f})")

        if re.fullmatch(r"[^a-zA-Z0-9]+", text):
            score = 0.0
            details.append("non-alphanumeric only")

        score = max(0.0, round(score, 2))
        return score, ", ".join(details)
