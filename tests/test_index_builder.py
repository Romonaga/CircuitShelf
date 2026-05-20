import logging
import unittest

import numpy as np

from index_builder import IndexBuilder
from state_manager import StateManager


class FakeChunker:
    def filter_chunks(self, chunks, sources, metadata, min_tokens=10, max_tokens=1000):
        kept = [
            (chunk, source, meta)
            for chunk, source, meta in zip(chunks, sources, metadata)
            if "DROP" not in chunk
        ]
        if not kept:
            return [], [], []
        out_chunks, out_sources, out_metadata = zip(*kept)
        return list(out_chunks), list(out_sources), list(out_metadata)


class FakeEmbedder:
    def encode(self, texts, batch_size=32, convert_to_numpy=True):
        return np.array(
            [[float(len(text)), float(sum(ord(char) for char in text) % 97)] for text in texts],
            dtype="float32",
        )


class BadShapeEmbedder:
    def encode(self, texts, batch_size=32, convert_to_numpy=True):
        return np.array([1.0, 2.0, 3.0], dtype="float32")


class IndexBuilderTests(unittest.TestCase):
    def setUp(self):
        self.logger = logging.getLogger("test-index-builder")
        self.logger.addHandler(logging.NullHandler())
        self.config = {
            "MIN_TOKENS_PER_CHUNK": 1,
            "MAX_TOKENS_PER_CHUNK": 1000,
            "EMBED_BATCH_SIZE": 2,
            "IMAGE_INDEX_MIN_CHARS": 5,
        }

    def test_build_filters_chunks_and_indexes_images(self):
        state = StateManager(use_lock=False)
        state.extend_chunks(
            ["Pin 1 goes to ground", "DROP bad chunk", "Pin 8 goes to VCC"],
            ["timer.pdf", "timer.pdf", "timer.pdf"],
            [{"page": 1}, {"page": 2}, {"page": 3}],
        )
        state.add_image_page_text("b-image", "555 timing diagram")
        state.add_image_page_text("a-image", "ok")

        result = IndexBuilder(state, FakeChunker(), FakeEmbedder(), self.config, self.logger).build()

        self.assertEqual(result.chunks, 2)
        self.assertEqual(result.dropped_chunks, 1)
        self.assertEqual(result.images, 1)
        self.assertEqual(state.get_chunks(), ["Pin 1 goes to ground", "Pin 8 goes to VCC"])
        self.assertEqual(state.get_sources(), ["timer.pdf", "timer.pdf"])
        self.assertEqual(state.get_metadata(), [{"page": 1}, {"page": 3}])
        self.assertEqual(len(state.get_embeddings()), 2)
        self.assertEqual(state.get_index().ntotal, 2)
        self.assertEqual(state.get_image_id_list(), ["b-image"])
        self.assertEqual(state.get_image_embeddings().ntotal, 1)

    def test_build_rejects_empty_chunk_state(self):
        state = StateManager(use_lock=False)

        with self.assertRaises(ValueError):
            IndexBuilder(state, FakeChunker(), FakeEmbedder(), self.config, self.logger).build()

    def test_build_rejects_invalid_embedding_shape(self):
        state = StateManager(use_lock=False)
        state.extend_chunks(["Pin 1 goes to ground"], ["timer.pdf"], [{"page": 1}])

        with self.assertRaises(ValueError):
            IndexBuilder(state, FakeChunker(), BadShapeEmbedder(), self.config, self.logger).build()


if __name__ == "__main__":
    unittest.main()
