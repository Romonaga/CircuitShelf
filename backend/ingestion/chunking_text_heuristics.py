import re


class TextHeuristicsMixin:
    def normalize_extracted_text(self, text: str) -> str:
        """Normalize PDF/OCR text before chunking without trying to understand it semantically."""
        normalized_lines = []
        for raw_line in text.replace("\r\n", "\n").replace("\r", "\n").splitlines():
            line = re.sub(r"\s+", " ", raw_line).strip()
            if not line:
                normalized_lines.append("")
                continue
            if self.is_low_value_line(line):
                continue
            normalized_lines.append(line)
        return "\n".join(normalized_lines).strip()

    def is_low_value_line(self, line: str) -> bool:
        lower = line.lower().strip()
        if not lower:
            return False
        if re.fullmatch(r"\d+", lower):
            return True
        if self.is_numeric_table_fragment(line):
            return True
        if self.is_package_table_fragment(line):
            return True
        if line.count(".") / max(1, len(line)) > 0.45:
            return True
        boilerplate = [
            "submit documentation feedback",
            "product folder links:",
            "copyright ©",
            "copyright (c)",
            "www.ti.com",
            "think of ways you could apply this knowledge",
        ]
        if any(item in lower for item in boilerplate):
            return True
        alpha_ratio = sum(char.isalpha() for char in line) / max(1, len(line))
        symbol_ratio = sum(not char.isalnum() and not char.isspace() for char in line) / max(1, len(line))
        return symbol_ratio > 0.65 and alpha_ratio < 0.15

    @staticmethod
    def is_numeric_table_fragment(line: str) -> bool:
        """Detect isolated numeric table cells that have no useful labels."""
        stripped = line.strip()
        if not stripped:
            return False
        if not re.search(r"\d", stripped):
            return False
        alpha_ratio = sum(char.isalpha() for char in stripped) / max(1, len(stripped))
        digit_ratio = sum(char.isdigit() for char in stripped) / max(1, len(stripped))
        allowed = re.fullmatch(r"[\d\s.,+\-−–/%()]+", stripped) is not None
        return allowed and digit_ratio > 0.28 and alpha_ratio < 0.08

    @staticmethod
    def is_package_table_fragment(line: str) -> bool:
        """Detect low-value packaging/order-code fragments common in datasheets."""
        tokens = [token.lower().strip("()[]{}.,;:") for token in re.split(r"\s+", line) if token.strip()]
        if not tokens:
            return False

        package_tokens = {
            "spq", "l", "w", "t", "b", "mm", "µm", "um", "tssop", "soic", "ssop",
            "pdip", "cdip", "sop", "so", "db", "ns", "nipdau", "green", "rohs",
            "non-rohs", "lead", "finish", "package", "orderable", "top-side", "marking",
        }
        package_token_count = sum(1 for token in tokens if token in package_tokens)
        has_package_token = package_token_count > 0
        has_digit = any(any(char.isdigit() for char in token) for token in tokens)
        short_or_package = sum(1 for token in tokens if token in package_tokens or len(token) <= 3)
        if (
            len(tokens) <= 12
            and has_package_token
            and (has_digit or package_token_count >= 2)
            and short_or_package / max(1, len(tokens)) >= 0.75
        ):
            return True
        if re.fullmatch(r"[A-Z0-9]{2,8}(?:\s*[|/]\s*[A-Z0-9]{1,8})+", line.strip()):
            return True
        return False

    def classify_line_type(self, line: str) -> str:
        lower = line.lower()
        if "=>" in line or re.search(r"\b[A-Z]{1,4}\d*\([A-Z+\-]+\)\s*=>", line):
            return "wiring"
        if re.search(r"\bfigure\s+\d+", lower):
            return "figure"
        if re.search(r"\b(table|parameter|conditions|typ|max|min|unit)\b", lower) and self.numeric_density(line) > 0.08:
            return "table"
        if self.score_equation_likelihood(line) >= 0.25:
            return "formula"
        if re.match(r"^[-*•]\s+", line) or re.match(r"^\d+[\).]\s+", line):
            return "list"
        return "paragraph"

    @staticmethod
    def numeric_density(text: str) -> float:
        return sum(char.isdigit() for char in text) / max(1, len(text))

    def is_heading(self, text: str) -> bool:
        s = text.strip()
        if not s or len(s.split()) > 12:
            return False
        if self.is_numeric_table_fragment(s) or self.is_package_table_fragment(s):
            return False
        if self.numeric_density(s) > 0.25:
            return False

        lower = s.lower().rstrip(":")
        strong_titles = {
            "applications",
            "features",
            "overview",
            "description",
            "design requirements",
            "detailed design procedure",
            "electrical characteristics",
            "absolute maximum ratings",
            "recommended operating conditions",
            "pin configuration and functions",
            "package materials information",
            "layout",
            "schematic",
            "parts list",
            "procedure",
            "operation",
            "notes",
        }
        strong_starts = [
            "section", "chapter", "appendix", "part", "module", "unit", "figure", "table",
            "application", "feature", "overview", "description", "design", "electrical",
            "pin configuration", "absolute maximum", "recommended operating",
        ]
        if lower in strong_titles or any(lower.startswith(word + " ") for word in strong_starts):
            return True
        if re.match(r"^\s*([A-Z]?[0-9]+(\.[0-9A-Z]+)*[\):]?)\s+[A-Z]", s):
            return True
        if re.match(r"^(NOTE|WARNING|CAUTION|SUMMARY|OBJECTIVE|GOAL|PURPOSE)\s*[:\-]", s, re.IGNORECASE):
            return True
        if s == s.upper() and 5 <= len(s) <= 100:
            words = s.split()
            meaningful_words = [word for word in words if len(word.strip("()[]{}.,;:")) > 3]
            return len(words) >= 2 and len(meaningful_words) >= 1
        return False

    def split_by_sections(self, text):
        section_pattern = re.compile(r"^(#+|[A-Z][^\n]{1,60})\n", re.MULTILINE)
        matches = list(section_pattern.finditer(text))

        sections = []
        for i, match in enumerate(matches):
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            title = match.group(0).strip()
            section_text = text[start:end].strip()
            sections.append((title, section_text))

        return sections if sections else [("Full Document", text)]
