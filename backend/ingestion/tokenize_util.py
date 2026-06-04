# tokenize_util.py

"""
@authors: sueco, rew
"""

import re
import numpy as np

class TokenUtils:
    def __init__(self, state, trace_logger=None):
        self.state = state
        self.logger = trace_logger

    @staticmethod
    def tokenize_len(text):
        if not text:
            return 0
        tokens = re.findall(r"\b\w+\b|[^\w\s]", text.lower())
        return len(tokens)

    @staticmethod
    def compute_average_tokens(chunks):
        if not chunks:
            return 0
        return sum(TokenUtils.tokenize_len(c) for c in chunks) / len(chunks)

    @staticmethod
    def estimate_token_density(text):
        tokens = TokenUtils.tokenize_len(text)
        words = len(text.split())
        return tokens / max(1, words)

    @staticmethod
    def sliding_window(sentences, chunk_size, overlap):
        """
        Generate token-aware overlapping windows of sentences.

        Parameters:
        -----------
        sentences : List[str]
            A list of pre-tokenized sentences to chunk.
        chunk_size : int
            The maximum number of tokens allowed per window (i.e., chunk).
        overlap : int
            The target number of overlapping tokens between consecutive windows.

        Returns:
        --------
        List[List[str]]
            A list of sentence windows, where each window is a list of sentences whose
            total token count does not exceed `chunk_size`.

        Notes:
        ------
        - Windows are created by aggregating sentences until the cumulative token count
        reaches `chunk_size`.
        - The window advances by `(chunk_size - overlap)` tokens for the next chunk.
        - Sentence boundaries are respected to preserve semantic integrity.
        """

        chunks = []
        i = 0
        while i < len(sentences):
            window = []
            token_total = 0
            j = i
            while j < len(sentences) and token_total + TokenUtils.tokenize_len(sentences[j]) <= chunk_size:
                token_total += TokenUtils.tokenize_len(sentences[j])
                window.append(sentences[j])
                j += 1
            if window:
                chunks.append(window)
            token_advance = 0
            while i < len(sentences) and token_advance < (chunk_size - overlap):
                token_advance += TokenUtils.tokenize_len(sentences[i])
                i += 1
        return chunks

    
    def normalize_token_distribution(self):
        state = self.state
        source_token_counts = {}
        for i, src in enumerate(state.sources):
            tok = TokenUtils.tokenize_len(state.chunks[i])
            source_token_counts[src] = source_token_counts.get(src, 0) + tok

        max_tokens = max(source_token_counts.values(), default=1)
        source_weights = {
            src: min(1.0, 0.75 * (max_tokens / count))
            for src, count in source_token_counts.items()
        }

        new_chunks, new_sources, new_meta = [], [], []
        for i in range(len(state.chunks)):
            src = state.sources[i]
            keep_prob = source_weights.get(src, 1.0)
            if np.random.rand() < keep_prob:
                new_chunks.append(state.chunks[i])
                new_sources.append(src)
                new_meta.append(state.chunk_metadata[i])

        removed = len(state.chunks) - len(new_chunks)
        if self.logger:
            self.logger.info(f"⚖️ Token normalization: kept {len(new_chunks)} chunks, removed {removed} over-weighted ones.")

        state.set_chunks(new_chunks)
        state.set_sources(new_sources)
        state.set_metadata(new_meta)
