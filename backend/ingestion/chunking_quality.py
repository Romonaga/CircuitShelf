import re

import numpy as np


class ChunkQualityMixin:
    def estimate_chunk_quality(self, text: str, chunk_type: str = "paragraph") -> tuple[float, list[str]]:
        stripped = text.strip()
        if not stripped:
            return 0.0, ["empty"]

        flags = []
        alpha_ratio = sum(char.isalpha() for char in stripped) / max(1, len(stripped))
        symbol_ratio = sum(not char.isalnum() and not char.isspace() for char in stripped) / max(1, len(stripped))
        dot_ratio = stripped.count(".") / max(1, len(stripped))
        digit_ratio = self.numeric_density(stripped)
        token_count = self.token_utils.tokenize_len(stripped)
        score = 1.0

        if dot_ratio > 0.25:
            score -= 0.55
            flags.append("dot_leader")
        structured_types = {"table", "formula", "wiring", "code"}
        if alpha_ratio < 0.18 and chunk_type not in structured_types:
            score -= 0.35
            flags.append("low_alpha")
        if symbol_ratio > 0.45 and chunk_type not in structured_types:
            score -= 0.35
            flags.append("symbol_heavy")
        if digit_ratio > 0.45 and alpha_ratio < 0.25 and chunk_type not in {"table", "formula", "code"}:
            score -= 0.55
            flags.append("numeric_heavy")
        if token_count < self.config.get("MIN_TOKENS_PER_CHUNK", 5):
            score -= 0.4
            flags.append("too_short")
        if re.search(r"\.{8,}", stripped):
            score -= 0.45
            flags.append("repeated_dots")

        return round(max(0.0, min(1.0, score)), 3), flags

    def make_chunk_meta(self, text: str, source_file: str, section: str, chunk_type: str) -> dict:
        category = self.categorize_chunk(text)
        quality_score, quality_flags = self.estimate_chunk_quality(text, chunk_type)
        if self.is_low_value_chunk(text, section, chunk_type):
            quality_score = 0.0
            quality_flags = sorted(set(quality_flags + ["low_value_chunk"]))
        return {
            "section": section,
            "page": 1,
            "source": source_file,
            "category": category,
            "chunk_type": chunk_type,
            "token_count": self.token_utils.tokenize_len(text),
            "quality_score": quality_score,
            "quality_flags": quality_flags,
        }

    def is_low_value_chunk(self, text: str, section: str = "", chunk_type: str = "paragraph") -> bool:
        stripped = text.strip()
        if not stripped:
            return True
        if chunk_type == "code":
            return not re.search(r"[A-Za-z_][A-Za-z0-9_]*", stripped)

        lower = stripped.lower()
        section_lower = str(section or "").lower()
        alpha_words = re.findall(r"[a-zA-Z]{2,}", stripped)
        electronics_terms = [
            "pin", "vcc", "gnd", "ground", "trigger", "threshold", "discharge", "reset",
            "output", "input", "timer", "timing", "capacitor", "resistor", "current", "voltage",
            "frequency", "duty", "oscillator", "monostable", "astable", "led", "diode",
            "transistor", "collector", "emitter", "base", "mosfet", "gate", "source", "drain",
        ]

        if len(alpha_words) < 2 and not any(term in lower for term in electronics_terms):
            return True

        package_sections = [
            "package outline",
            "package materials information",
            "package option addendum",
            "packaging information",
            "ceramic dual-in-line",
            "example board layout",
            "land pattern",
        ]
        if any(item in section_lower for item in package_sections):
            return not any(term in lower for term in electronics_terms)

        if chunk_type == "table" and self.numeric_density(stripped) > 0.35 and not any(term in lower for term in electronics_terms):
            return True

        if re.fullmatch(r"\d{1,2}[-/][A-Za-z]{3}[-/]\d{2,4}", stripped):
            return True

        return False

    def categorize_chunk(self, text: str) -> str:
        chunk_cats = self.config.get("CHUNK_CATEGORIES", {})
        lower_text = text.lower()
        scored_categories = []
        for category, data in chunk_cats.items():
            score = 0
            for keyword in data.get("keywords", []):
                keyword = str(keyword).lower()
                if keyword.lower() in lower_text:
                    score += 1
            if score:
                scored_categories.append((score, self.category_priority(category), category))
        if not scored_categories:
            return "General Information"
        scored_categories.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return scored_categories[0][2]

    @staticmethod
    def category_priority(category: str) -> int:
        category_upper = category.upper()
        if "TECH" in category_upper:
            return 30
        if "MED" in category_upper:
            return 20
        if "HIGH" in category_upper:
            return 10
        return 0

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

    def filter_chunks(self, chunks, sources, metadata, min_tokens=10, max_tokens=1000):
        """Filters out low-quality, short, long, or junk chunks while maintaining alignment."""
        filtered_chunks = []
        filtered_sources = []
        filtered_metadata = []
        dropped_count = 0
        min_quality = self.config.get("MIN_CHUNK_QUALITY", 0.15)

        for chunk, src, meta in zip(chunks, sources, metadata):
            tok_len = self.token_utils.tokenize_len(chunk)
            stripped = chunk.strip()
            is_junk = not stripped or not re.search(r"[A-Za-z0-9]", stripped)
            quality_score = meta.get("quality_score", 1.0) if isinstance(meta, dict) else 1.0
            low_quality = quality_score < min_quality

            if min_tokens <= tok_len <= max_tokens and not is_junk and not low_quality:
                filtered_chunks.append(chunk)
                filtered_sources.append(src)
                filtered_metadata.append(meta)
            else:
                dropped_count += 1
                reason = "Junk" if is_junk else "Low quality" if low_quality else "Token count out of range"
                self.trace_logger.debug(
                    f"🚫 Dropped chunk from '{src}' | Tokens: {tok_len} | "
                    f"Quality: {quality_score:.2f} | Reason: {reason} | "
                    f"Preview: {chunk[:80].strip()}"
                )

        self.trace_logger.debug(f"Chunk filtering complete. Kept {len(filtered_chunks)} | Dropped {dropped_count}")
        return filtered_chunks, filtered_sources, filtered_metadata

    def compute_confidence(self, top_score, second_score, method="sigmoid_margin", alpha=4.0, beta=2.0, min_floor=0.2):
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

    def build_chunk_payload(self, selected_hits):
        payload = []
        for i, d in selected_hits:
            meta = self.state.chunk_metadata[i]
            payload.append({
                "text": self.state.chunks[i],
                "index": i,
                "distance": d,
                "section": meta.get("section", "Unknown"),
                "source": meta.get("parent_source") or meta.get("source") or self.state.sources[i],
                "source_image_id": meta.get("source_image_id"),
                "page": meta.get("page"),
                "category": meta.get("category", "Uncategorized")
            })
        return payload

    @staticmethod
    def compute_vector_confidence(selected_hits, dist_thresh):
        avg_dist = np.mean([d for _, d in selected_hits])
        return f"{max(0.2, 1 - avg_dist / dist_thresh):.2f}"
