import re


class MathDetectionMixin:
    def score_equation_likelihood(self, text: str) -> float:
        if not text or not isinstance(text, str):
            return 0.0

        text = text.strip().lower()
        eq_config = self.config.get("EQUATION_DETECTION", {})
        math_tokens = eq_config.get("MATH_SYMBOLS", [])
        keywords = eq_config.get("KEYWORDS", [])

        symbol_count = sum(text.count(sym) for sym in math_tokens)
        keyword_count = sum(1 for kw in keywords if kw in text)

        length_factor = min(len(text) / 200, 1.0)
        raw_score = 0.5 * (symbol_count / 5) + 0.5 * (keyword_count / 2)
        return round(min(1.0, raw_score * length_factor), 3)

    def detect_variable_definition(self, line):
        eq_config = self.config.get("EQUATION_DETECTION", {})
        patterns = eq_config.get("MATH_VARIABLE_DEFINITION_PATTERNS", [])
        return any(re.match(pat, line.strip(), re.IGNORECASE) for pat in patterns)

    def is_math_heavy_question(self, question: str) -> bool:
        question = question.lower()

        math_cfg = self.config.get("EQUATION_DETECTION", {})
        symbols = math_cfg.get("MATH_SYMBOLS", [])
        keywords = math_cfg.get("KEYWORDS", [])

        if not symbols and not keywords:
            self.trace_logger.warning("⚠️ EQUATION_DETECTION config is missing or empty.")
            return False

        self.trace_logger.debug(f"🔍 Checking math question heuristics for: '{question}'")

        keyword_matches = [str(kw).lower() for kw in keywords if str(kw).lower() in question]
        keyword_hit = bool(keyword_matches)

        if keyword_hit:
            self.trace_logger.debug(f"✅ Matched math keywords: {keyword_matches}")
        else:
            self.trace_logger.debug("❌ No keyword matches")

        symbol_hit = False
        for sym in symbols:
            try:
                if re.search(sym, question):
                    self.trace_logger.debug(f"✅ Regex match: '{sym}'")
                    symbol_hit = True
                    break
            except re.error as exc:
                self.trace_logger.warning(f"⚠️ Invalid regex in config: '{sym}' → {exc}")

        if not symbol_hit:
            self.trace_logger.debug("❌ No regex symbol matches")

        if keyword_hit or symbol_hit:
            self.trace_logger.info(f"🧠 Math-heavy question detected: '{question}'")
        else:
            self.trace_logger.info(f"🧠 Non-math question: '{question}'")

        return keyword_hit or symbol_hit

    def is_math_heavy(self, text):
        text = text.lower().strip()
        score = 0
        eq_config = self.config.get("EQUATION_DETECTION", {})
        math_symbols = eq_config.get("MATH_SYMBOLS", [])
        math_keywords = eq_config.get("KEYWORDS", [])
        variable_patterns = eq_config.get("MATH_VARIABLE_DEFINITION_PATTERNS", [])
        for pat in variable_patterns:
            score += len(re.findall(pat, text))
        score += 2 * sum(kw in text for kw in math_keywords)
        score += sum(text.count(sym) for sym in math_symbols)
        latex_triggers = ["\\begin{equation}", "\\frac", "\\sum", "\\int", "$"]
        if any(pat in text for pat in latex_triggers):
            score += 3
        structure_patterns = [
            r"how do i solve", r"what is the solution", r"formulate.*problem",
            r"given.*optimize", r"compute.*optimal", r"derive.*expression",
            r"what math"
        ]
        score += 3 * sum(bool(re.search(pat, text)) for pat in structure_patterns)
        self.trace_logger.debug(f"is_math_heavy scored this as socre: {score}")
        return score >= 5
