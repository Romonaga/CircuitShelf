# chunking_util.py

"""
@authors: sueco, rew
"""


import re
from nltk.tokenize import sent_tokenize

from backend.ingestion.chunking_math import MathDetectionMixin
from backend.ingestion.chunking_ocr_quality import OcrQualityMixin
from backend.ingestion.chunking_quality import ChunkQualityMixin
from backend.ingestion.chunking_text_heuristics import TextHeuristicsMixin


class ChunkingUtils(TextHeuristicsMixin, MathDetectionMixin, ChunkQualityMixin, OcrQualityMixin):
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

    def split_lines_to_budget(self, lines, chunk_size, overlap):
        chunks = []
        i = 0
        while i < len(lines):
            current = []
            token_total = 0
            j = i
            while j < len(lines):
                line_tokens = self.token_utils.tokenize_len(lines[j])
                if current and token_total + line_tokens > chunk_size:
                    break
                current.append(lines[j])
                token_total += line_tokens
                j += 1

            if not current:
                current = [lines[i]]
                j = i + 1
            chunks.append("\n".join(current).strip())

            if overlap <= 0 or j >= len(lines):
                i = j
                continue

            overlap_tokens = 0
            rewind = j
            while rewind > i and overlap_tokens < overlap:
                rewind -= 1
                overlap_tokens += self.token_utils.tokenize_len(lines[rewind])
            i = max(rewind, i + 1)
        return [chunk for chunk in chunks if chunk]

    def deterministic_chunk_text(self, text, source_file, chunk_size, overlap):
        cleaned = self.normalize_extracted_text(text)
        if not cleaned:
            return [], []

        blocks = []
        current_section = "Untitled Section"
        current_lines = []
        current_type = None

        def flush_block():
            nonlocal current_lines, current_type
            if current_lines:
                blocks.append({
                    "section": current_section,
                    "type": current_type or "paragraph",
                    "lines": current_lines,
                })
            current_lines = []
            current_type = None

        for line in cleaned.splitlines():
            if not line.strip():
                flush_block()
                continue
            if self.is_heading(line):
                flush_block()
                current_section = line.strip()
                continue

            line_type = self.classify_line_type(line)
            if current_lines and line_type != current_type and line_type in {"table", "formula", "wiring", "figure"}:
                flush_block()
            current_type = current_type or line_type
            current_lines.append(line)

        flush_block()

        chunks_out, meta = [], []
        buffer_lines = []
        buffer_section = None
        buffer_type = None

        def flush_buffer():
            nonlocal buffer_lines, buffer_section, buffer_type
            if not buffer_lines:
                return
            for chunk in self.split_lines_to_budget(buffer_lines, chunk_size, overlap):
                chunks_out.append(chunk)
                meta.append(self.make_chunk_meta(chunk, source_file, buffer_section or "Untitled Section", buffer_type or "paragraph"))
            buffer_lines = []
            buffer_section = None
            buffer_type = None

        for block in blocks:
            block_lines = block["lines"]
            block_type = block["type"]
            block_section = block["section"]
            block_tokens = self.token_utils.tokenize_len("\n".join(block_lines))
            combinable = block_type in {"paragraph", "list"} and block_tokens < chunk_size

            if combinable:
                candidate = buffer_lines + [""] + block_lines if buffer_lines else block_lines
                same_section = buffer_section in {None, block_section}
                if same_section and self.token_utils.tokenize_len("\n".join(candidate)) <= chunk_size:
                    buffer_lines = candidate
                    buffer_section = block_section
                    buffer_type = block_type if buffer_type is None else buffer_type
                    continue

            flush_buffer()
            for chunk in self.split_lines_to_budget(block_lines, chunk_size, overlap):
                chunks_out.append(chunk)
                meta.append(self.make_chunk_meta(chunk, source_file, block_section, block_type))

        flush_buffer()
        return chunks_out, meta
            

    def smart_chunk_text(self, text, source_file, force_math=False, chunk_size=None, overlap=None):
        self.trace_logger.debug(f"Using smart_chunk_text for {source_file}")
        chunks_out, meta = [], []
        
        if(chunk_size is None):
            chunk_size = self.config.get("CHUNK_SIZE")

        if(overlap is None):
            overlap  =  self.config.get("CHUNK_OVERLAP")

        text = self.normalize_extracted_text(text)
        if not text:
            return [], []
    

        enable_math_chunking = self.config.get("ENABLE_MATH_HEAVY_CHUNKING", False)
        if enable_math_chunking and not force_math and self.is_math_heavy(text):
            force_math = True            
            self.trace_logger.info(f"🔍 Auto-detected math-heavy content in {source_file}. Switching to math chunking.")

        if not force_math and self.config.get("CHUNKING_MODE", "deterministic") == "deterministic":
            self.trace_logger.debug(f"Deterministic page chunking for {source_file}")
            return self.deterministic_chunk_text(text, source_file, chunk_size, overlap)

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
