# chunking_util.py

"""
@authors: sueco, rew
"""


import re
import numpy as np
from nltk.tokenize import sent_tokenize


class ChunkingUtils:
    def __init__(self, state, token_utils, trace_logger=None, config=None):
        self.state = state
        self.token_utils = token_utils
        self.trace_logger = trace_logger
        self.config = config
        
        self.scoring_heurustics = self.config.get('SCORING_HEURISTICS', {})
        self.chunk_categories = self.config.get('CHUNK_CATEGORIES', {})
        self.equation_detection = self.config.get('EQUATION_DETECTION', {})

        self.trace_logger.debug(f"🔧 Loaded SCORING_HEURISTICS: {self.scoring_heurustics}")
        self.trace_logger.debug(f"📊 Loaded CHUNK_CATEGORIES: {self.chunk_categories}")
        self.trace_logger.debug(f"📊 Loaded EQUATION_DETECTION: {self.equation_detection}")
            

    def smart_chunk_text(self, text, source_file, force_math=False, chunk_size=None, overlap=None):
        self.trace_logger.info(f"📀 Using smart_chunk_text for {source_file}")
        chunks_out, meta = [], []
        
        if(chunk_size is None):
            chunk_size = self.config.get("CHUNK_SIZE")

        if(overlap is None):
            overlap  =  self.config.get("CHUNK_OVERLAP")
    

        enable_math_chunking = self.config.get("ENABLE_MATH_HEAVY_CHUNKING", False)
        if enable_math_chunking and not force_math and self.is_math_heavy(text):
            force_math = True            
            self.trace_logger.info(f"🔍 Auto-detected math-heavy content in {source_file}. Switching to math chunking.")

        if force_math:
            self.trace_logger.info(f"📀 Math-mode chunking for {source_file}")
            chunk_size = 400
            overlap = 100

            blocks = re.split(r'\n(?=#)', text)
            blocks = [b.strip() for b in blocks if b.strip()]
            page_num = 1

            for block in blocks:
                lines = [l.strip() for l in block.splitlines() if l.strip()]
                i = 0
                while i < len(lines):
                    token_total = 0
                    chunk_lines = []
                    j = i
                    while j < len(lines):
                        tokens = self.token_utils.tokenize_len(lines[j])
                        if token_total + tokens > chunk_size:
                            break
                        chunk_lines.append(lines[j])
                        token_total += tokens
                        j += 1

                    for line in chunk_lines:
                        section = "Variable Definition" if self.detect_variable_definition(line) else "Math Section"
                        category = self.categorize_chunk(line)
                        chunks_out.append(line)
                        meta.append({
                            "section": section,
                            "page": page_num,
                            "source": source_file,
                            "category": category
                        })

                    token_advance = 0
                    while i < len(lines) and token_advance < (chunk_size - overlap):
                        token_advance += self.token_utils.tokenize_len(lines[i])
                        i += 1

        else:
            
            self.trace_logger.info(f"🧱 Section-aware chunking for {source_file}")

            current_section = "Untitled Section"
            page_num = 1
            blocks = [b.strip() for b in re.split(r'(?:\n\s*\n|\n[-*_]{3,}\n)', text) if b.strip()]

            for block in blocks:
                if self.is_heading(block):
                    current_section = block.strip()
                    continue

                sentences = sent_tokenize(block)
                for sentence_window in self.token_utils.sliding_window(sentences, chunk_size, overlap):
                    chunk_text = " ".join(sentence_window)
                    category = self.categorize_chunk(chunk_text)
                    meta.append({
                        "section": current_section,
                        "page": page_num,
                        "source": source_file,
                        "category": category
                    })
                    chunks_out.append(chunk_text)

        return chunks_out, meta

    def smart_chunk_pages(self, page_texts, source_file, force_math=False, chunk_size=None, overlap=None):
        """Chunk PDF text one page at a time so metadata keeps real page numbers."""
        chunks_out, meta = [], []

        for page_num, page_text in enumerate(page_texts, start=1):
            if not page_text or not page_text.strip():
                continue

            page_chunks, page_meta = self.smart_chunk_text(
                page_text,
                source_file,
                force_math=force_math,
                chunk_size=chunk_size,
                overlap=overlap,
            )

            for item in page_meta:
                item["page"] = page_num
                item["source"] = source_file

            chunks_out.extend(page_chunks)
            meta.extend(page_meta)

        return chunks_out, meta

    def adaptive_chunk_pages(self, page_texts, source_file):
        """Adaptive chunking variant that preserves PDF page metadata."""
        chunks_out, meta = [], []

        for page_num, page_text in enumerate(page_texts, start=1):
            if not page_text or not page_text.strip():
                continue

            page_chunks, page_meta = self.adaptive_chunk_text(page_text, source_file)
            for item in page_meta:
                item["page"] = page_num
                item["source"] = source_file

            chunks_out.extend(page_chunks)
            meta.extend(page_meta)

        return chunks_out, meta

    
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

    def is_heading(self, text: str) -> bool:
        s = text.strip()
        if not s or len(s.split()) > 12:
            return False
        if s == s.upper() and 5 <= len(s) <= 100:
            return True
        strong_starts = ["section", "chapter", "appendix", "part", "module", "unit", "figure", "table"]
        if any(s.lower().startswith(word + " ") for word in strong_starts):
            return True
        if re.match(r"^\s*([A-Z]?[0-9]+(\.[0-9A-Z]+)*[\):]?)\s+[A-Z]", s):
            return True
        if re.match(r"^(NOTE|WARNING|CAUTION|SUMMARY|OBJECTIVE|GOAL|PURPOSE)\s*[:\-]", s, re.IGNORECASE):
            return True
        if s.istitle() and len(s.split()) <= 6:
            return True
        return False

    def categorize_chunk(self, text: str) -> str:
        chunk_cats = self.config.get("CHUNK_CATEGORIES", {})
        lower_text = text.lower()
        for category, data in chunk_cats.items():
            for keyword in data.get("keywords", []):
                if keyword.lower() in lower_text:
                    return category
        return "General Information"

 

    def is_math_heavy_question(self, question: str) -> bool:
        question = question.lower()

        math_cfg = self.config.get("EQUATION_DETECTION", {})
        symbols = math_cfg.get("MATH_SYMBOLS", [])
        keywords = math_cfg.get("KEYWORDS", [])

        if not symbols and not keywords:
            self.trace_logger.warning("⚠️ EQUATION_DETECTION config is missing or empty.")
            return False

        self.trace_logger.debug(f"🔍 Checking math question heuristics for: '{question}'")

        # Check for math-related keywords
        keyword_matches = [kw for kw in keywords if kw.lower() in question]
        keyword_hit = bool(keyword_matches)

        if keyword_hit:
            self.trace_logger.debug(f"✅ Matched math keywords: {keyword_matches}")
        else:
            self.trace_logger.debug("❌ No keyword matches")

        # Check for symbolic or pattern-based hits
        symbol_hit = False
        for sym in symbols:
            try:
                if re.search(sym, question):
                    self.trace_logger.debug(f"✅ Regex match: '{sym}'")
                    symbol_hit = True
                    break
            except re.error as e:
                self.trace_logger.warning(f"⚠️ Invalid regex in config: '{sym}' → {e}")

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

    def compute_chunk_category(self, heading: str, text: str) -> str:
        
        length_penalty = self.scoring_heurustics.get("LENGTH_PENALTY", {"short": 1.5, "long": -1.5})
        symbol_thresh = self.scoring_heurustics.get("SYMBOL_THRESHOLD", 5)
        symbol_penalty = self.scoring_heurustics.get("SYMBOL_PENALTY", -0.5)
        num_thresh = self.scoring_heurustics.get("NUMERIC_DENSITY_THRESHOLD", 0.1)
        num_penalty = self.scoring_heurustics.get("NUMERIC_DENSITY_PENALTY", -0.5)
        math_symbols = self.config.get("EQUATION_DETECTION", {}).get("MATH_SYMBOLS", [])

        
        h, t = heading.lower(), text.lower()
        score = 0

        high = self.chunk_categories.get("HIGH_LEVEL_DETAIL", ["purpose", "overview", "mission", "objective", "summary", "goal"])
        mid = self.chunk_categories.get("MED_LEVEL_DETAIL", ["system", "framework", "architecture", "workflow", "component"])
        tech = self.chunk_categories.get("TECH_LEVEL_DETAIL", ["constraint", "variable", "minimize", "optimization", "equation"])

        score += sum(3 for kw in high if kw in h)
        score += sum(1.5 for kw in mid if kw in h)
        score -= sum(2 for kw in tech if kw in h)

        word_count = self.token_utils.tokenize_len(t)
        math_penalty = -1 if any(kw in t for kw in tech) else 0
        symbol_count = len(re.findall(math_symbols, t))
        numeric_density = sum(1 for w in t.split() if w.isnumeric()) / max(1, word_count)

        score += length_penalty.get("short", 1.5) if word_count < 300 else length_penalty.get("long", -1.5) if word_count > 700 else 0
        score += math_penalty
        score -= symbol_penalty if symbol_count > symbol_thresh else 0
        score -= num_penalty if numeric_density > num_thresh else 0
        
        self.trace_logger.debug(f"🧩 [CHUNK CAT] heading='{heading[:30]}' tokens={word_count} symbols={symbol_count} density={numeric_density:.2f} score={score:.2f}")
        if score >= 3.5:
            return "High-level Summary"
        elif score >= 0.5:
            return "Medium-level Detail"
        return "Technical Detail"

    def evaluate_ocr_quality(self, text, ocr_confidence=None):
        text = text.strip()
        if not text:
            return 0.0, "Empty"

        unique_chars = len(set(text))
        words = text.split()
        avg_word_len = np.mean([len(w) for w in words]) if words else 0
        alpha_ratio = sum(c.isalpha() for c in text) / len(text)
        digit_ratio = sum(c.isdigit() for c in text) / len(text)
        space_ratio = sum(c.isspace() for c in text) / len(text)
        symbol_ratio = sum(not c.isalnum() and not c.isspace() for c in text) / len(text)

        # Load thresholds from config (or use defaults)
        min_length = self.config.get("OCR_MIN_LENGTH", 20)
        min_unique_chars = self.config.get("OCR_MIN_UNIQUE_CHARS", 10)
        max_avg_word_len = self.config.get("OCR_MAX_AVG_WORD_LEN", 12)
        min_alpha_ratio = self.config.get("OCR_MIN_ALPHA_RATIO", 0.3)
        max_symbol_ratio = self.config.get("OCR_MAX_SYMBOL_RATIO", 0.4)
        max_digit_ratio = self.config.get("OCR_MAX_DIGIT_RATIO", 0.5)
        max_space_ratio = self.config.get("OCR_MAX_SPACE_RATIO", 0.3)
        min_confidence = self.config.get("OCR_MIN_CONFIDENCE", 25)

        score = 1.0
        details = []

        if len(text) < min_length:
            score -= 0.4
            details.append("too short")

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


    def filter_chunks(self, chunks, sources, metadata, min_tokens=10, max_tokens=1000):
        """Filters out low-quality, short, long, or junk chunks while maintaining alignment."""
        filtered_chunks = []
        filtered_sources = []
        filtered_metadata = []
        dropped_count = 0

        for chunk, src, meta in zip(chunks, sources, metadata):
            tok_len = self.token_utils.tokenize_len(chunk)
            stripped = chunk.strip()
            is_junk = not stripped or not re.search(r"[A-Za-z0-9]", stripped)

            if min_tokens <= tok_len <= max_tokens and not is_junk:
                filtered_chunks.append(chunk)
                filtered_sources.append(src)
                filtered_metadata.append(meta)
            else:
                dropped_count += 1
                
                self.trace_logger.debug(
                    f"🚫 Dropped chunk from '{src}' | Tokens: {tok_len} | "
                    f"Reason: {'Junk' if is_junk else 'Token count out of range'} | "
                    f"Preview: {chunk[:80].strip()}"
                )


        self.trace_logger.info(f"🧹 Chunk filtering complete. Kept {len(filtered_chunks)} | Dropped {dropped_count}")
        return filtered_chunks, filtered_sources, filtered_metadata

    def compute_confidence(self, top_score, second_score, method="sigmoid_margin", alpha=4.0, beta=2.0, min_floor=0.2):
        """
        Compute a confidence score based on top and second scores using one of several methods.

        Parameters:
            method: "linear_margin" | "sigmoid_margin" | "normalized_ratio"
            alpha: tuning factor for sigmoid slope
            beta: tuning offset for sigmoid bias
            min_floor: lower bound for confidence

        Returns:
            confidence float ∈ [0, 1]
        """
        margin = top_score - second_score

        if method == "linear_margin":
            raw = 0.6 * top_score + 0.4 * margin
        elif method == "normalized_ratio":
            if top_score == 0:
                return min_floor
            raw = margin / top_score
        elif method == "sigmoid_margin":
            x = alpha * (top_score + 0.5 * margin) - beta
            raw = 1 / (1 + np.exp(-x))
        else:
            self.trace_logger.warning(f"⚠️ Unknown confidence method: {method}, returning min_floor: {min_floor}")
            return min_floor

        return round(max(min_floor, min(1.0, raw)), 4)

    # Helper functions (modularize internal steps)
    def build_chunk_payload(self, selected_hits):
        return [{
            "text": self.state.chunks[i],
            "index": i,
            "distance": d,
            "section": self.state.chunk_metadata[i].get("section", "Unknown"),
            "source": self.state.sources[i],
            "category": self.state.chunk_metadata[i].get("category", "Uncategorized")
        } for i, d in selected_hits]

    def compute_faiss_confidence(self, selected_hits, dist_thresh):
        avg_dist = np.mean([d for _, d in selected_hits])
        return f"{max(0.2, 1 - avg_dist / dist_thresh):.2f}"


    def adaptive_chunk_text(self, text, docname):
        self.trace_logger.info(f"📀 Using adaptive_chunk_text for {docname}")
        base_chunk_size = self.config.get("CHUNK_SIZE", 500)
        overlap = self.config.get("CHUNK_OVERLAP", 50)

        density = self.token_utils.estimate_token_density(text)

        # Adjust chunk size based on density
        if density < 10:
            chunk_size = int(base_chunk_size * 1.5)  # sparse → larger chunks
        elif density > 40:
            chunk_size = int(base_chunk_size * 0.75)  # dense → smaller chunks
        else:
            chunk_size = base_chunk_size

        # Apply section-aware splitting
        sections = self.split_by_sections(text)
        all_chunks, all_meta = [], []

        for section_title, section_text in sections:
            chunks, meta = self.smart_chunk_text(section_text, docname, chunk_size=chunk_size, overlap=overlap)
            for m in meta:
                m["section_header"] = section_title
            all_chunks.extend(chunks)
            all_meta.extend(meta)

        return all_chunks, all_meta


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
