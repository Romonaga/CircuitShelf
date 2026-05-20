"""Build FAISS indexes from prepared chunks and OCR text."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import faiss
import numpy as np


@dataclass(frozen=True)
class IndexBuildResult:
    chunks: int
    dropped_chunks: int
    images: int
    embedding_dim: int


class IndexBuilder:
    """Small, testable index-building layer.

    This class assumes ingestion has already populated StateManager with chunks,
    sources, metadata, and optional image OCR text.
    """

    def __init__(self, state, chunker, embedder, config: dict[str, Any], logger):
        self.state = state
        self.chunker = chunker
        self.embedder = embedder
        self.config = config
        self.logger = logger

    def build(self) -> IndexBuildResult:
        raw_chunks = self.state.get_chunks()
        raw_sources = self.state.get_sources()
        raw_metadata = self.state.get_metadata()

        if not raw_chunks:
            raise ValueError("No valid chunks found. Cannot build index.")

        min_tokens = self.config.get("MIN_TOKENS_PER_CHUNK", 10)
        max_tokens = self.config.get("MAX_TOKENS_PER_CHUNK", 1000)
        filtered_chunks, filtered_sources, filtered_metadata = self.chunker.filter_chunks(
            raw_chunks,
            raw_sources,
            raw_metadata,
            min_tokens=min_tokens,
            max_tokens=max_tokens,
        )

        if not filtered_chunks:
            raise ValueError("All chunks were filtered out. Cannot build index.")

        dropped = len(raw_chunks) - len(filtered_chunks)
        if dropped:
            self.logger.warning(f"⚠️ Dropped {dropped} chunks outside token range [{min_tokens}, {max_tokens}].")

        embeddings = self._encode(filtered_chunks)
        faiss_index = self._build_faiss_index(embeddings)

        self.state.set_chunks(filtered_chunks)
        self.state.set_sources(filtered_sources)
        self.state.set_metadata(filtered_metadata)
        self.state.set_embeddings(embeddings)
        self.state.set_index(faiss_index)

        image_count = self._build_image_index()
        return IndexBuildResult(
            chunks=len(filtered_chunks),
            dropped_chunks=dropped,
            images=image_count,
            embedding_dim=int(embeddings.shape[1]),
        )

    def _build_image_index(self) -> int:
        image_text = self.state.get_image_page_text()
        min_chars = self.config.get("IMAGE_INDEX_MIN_CHARS", self.config.get("OCR_MIN_LENGTH", 20))
        image_ids = sorted(key for key, value in image_text.items() if len(value.strip()) >= min_chars)

        if not image_ids:
            self.state.set_image_id_list([])
            self.state.set_image_embeddings(None)
            self.logger.info("ℹ️ No image OCR text met indexing criteria.")
            return 0

        ocr_texts = [image_text[key] for key in image_ids]
        image_embeddings = self._encode(ocr_texts)
        image_index = self._build_faiss_index(image_embeddings)

        self.state.set_image_id_list(image_ids)
        self.state.set_image_embeddings(image_index)
        self.logger.info(f"✅ OCR image index built: {len(image_ids)} entries")
        return len(image_ids)

    def _encode(self, texts: list[str]) -> np.ndarray:
        batch_size = self.config.get("EMBED_BATCH_SIZE", 32)
        embeddings = self.embedder.encode(texts, batch_size=batch_size, convert_to_numpy=True)
        embeddings = np.asarray(embeddings, dtype="float32")
        if embeddings.ndim != 2 or embeddings.shape[0] != len(texts):
            raise ValueError(f"Embedder returned invalid shape {embeddings.shape} for {len(texts)} texts.")
        return embeddings

    @staticmethod
    def _build_faiss_index(embeddings: np.ndarray):
        if embeddings.ndim != 2 or embeddings.shape[0] == 0:
            raise ValueError("Cannot build FAISS index from empty embeddings.")
        index = faiss.IndexFlatL2(embeddings.shape[1])
        index.add(embeddings)
        return index
