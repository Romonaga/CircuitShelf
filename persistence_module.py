# persistence_module.py

"""
@authors: sueco, rew
"""
import os
import pickle
import faiss
from dataclasses import dataclass
from typing import List

@dataclass
class PersistenceConfig:
    cache_file: str
    embeddings_file: str
    index_file: str
    chunks_file: str
    sources_file: str
    metadata_file: str
    image_store_file: str
    image_captions_file: str
    image_page_text_file: str
    image_ids_file: str
    image_embeddings_file: str


class PersistenceManager:
    def __init__(self, state, logger, config: PersistenceConfig):
        self.state = state
        self.logger = logger
        self.config = config

    def save_all(self):
        self.logger.info("💾 Saving all state to disk...")

        try:
            with open(self.config.cache_file, "wb") as f:
                pickle.dump(self.state.get_cache(), f)
            self.logger.info("💾 Cache saved.")
        except Exception as e:
            self.logger.warning(f"⚠️ Failed to save cache: {e}")

        try:
            with open(self.config.embeddings_file, "wb") as f:
                pickle.dump(self.state.get_embeddings(), f)
            self.logger.info("💾 Embeddings saved.")
        except Exception as e:
            self.logger.warning(f"⚠️ Failed to save embeddings: {e}")

        try:
            index = self.state.get_index()
            if index is not None:
                faiss.write_index(index, self.config.index_file)
                self.logger.info("💾 FAISS index saved.")
        except Exception as e:
            self.logger.warning(f"⚠️ Failed to save FAISS index: {e}")

        self._save_pickle_data(self.config.chunks_file, self.state.get_chunks, "chunks")
        self._save_pickle_data(self.config.sources_file, self.state.get_sources, "sources")
        self._save_pickle_data(self.config.metadata_file, self.state.get_metadata, "metadata")
        self._save_pickle_data(self.config.image_store_file, self.state.get_image_store, "image_store")
        self._save_pickle_data(self.config.image_captions_file, self.state.get_image_captions, "image_captions")
        self._save_pickle_data(self.config.image_page_text_file, self.state.get_image_page_text, "image_page_text")
        self._save_pickle_data(self.config.image_ids_file, self.state.get_image_id_list, "image_ids")

        try:
            image_index = self.state.get_image_embeddings()
            if image_index is not None:
                faiss.write_index(image_index, self.config.image_embeddings_file)
                self.logger.info("💾 Image FAISS index saved.")
        except Exception as e:
            self.logger.warning(f"⚠️ Failed to save image FAISS index: {e}")

        try:
            chunks = self.state.get_chunks()
            embeddings = self.state.get_embeddings()
            image_ids = self.state.get_image_id_list()
            self.logger.info(f"📦 Save summary: {len(chunks)} chunks, {len(embeddings)} embeddings, {len(image_ids)} images.")
        except Exception as e:
            self.logger.warning(f"⚠️ Failed to log save summary: {e}")

        self.logger.info("💾✅ All state saved successfully.")

    def load_all(self):
        self.logger.info("📂 Loading all state from disk...")

        try:
            with open(self.config.cache_file, "rb") as f:
                loaded_cache = pickle.load(f)
                self.state.set_cache(loaded_cache)
                self.logger.info("   ✅ Cache loaded.")
        except FileNotFoundError:
            self.logger.warning("⚠️ Cache file not found. Starting fresh.")
        except Exception as e:
            self.logger.warning(f"⚠️ Failed to load cache: {e}")

        self._load_pickle_data(self.config.embeddings_file, self.state.set_embeddings, "embeddings")
        self._load_pickle_data(self.config.chunks_file, self.state.set_chunks, "chunks")
        self._load_pickle_data(self.config.sources_file, self.state.set_sources, "sources")
        self._load_pickle_data(self.config.metadata_file, self.state.set_metadata, "metadata")
        self._load_pickle_data(self.config.image_store_file, self.state.set_image_store, "image_store")
        self._load_pickle_data(self.config.image_captions_file, self.state.set_image_captions, "image_captions")
        self._load_pickle_data(self.config.image_page_text_file, self.state.set_image_page_text, "image_page_text")
        self._load_pickle_data(self.config.image_ids_file, self.state.set_image_id_list, "image_ids")

        if os.path.exists(self.config.index_file):
            try:
                self.state.set_index(faiss.read_index(self.config.index_file))
                self.logger.info("   ✅ FAISS index loaded.")
            except Exception as e:
                self.logger.warning(f"⚠️ Failed to load FAISS index: {e}")

        if os.path.exists(self.config.image_embeddings_file):
            try:
                self.state.set_image_embeddings(faiss.read_index(self.config.image_embeddings_file))
                self.logger.info("   ✅ Image FAISS index loaded.")
            except Exception as e:
                self.logger.warning(f"⚠️ Failed to load image FAISS index: {e}")

        self.logger.debug(
            f"Post-load From Disk: {len(self.state.get_chunks())} chunks, "
            f"{len(self.state.get_sources())} sources, "
            f"{len(self.state.get_metadata())} metadata"
        )

        self.logger.info("📂 All state restored from disk.")

    def ensure_directories(self, additional_paths: List[str] = None):
        paths = [
            self.config.index_file, self.config.chunks_file, self.config.sources_file, self.config.metadata_file,
            self.config.embeddings_file, self.config.image_store_file, self.config.image_captions_file,
            self.config.image_page_text_file, self.config.image_embeddings_file, self.config.image_ids_file,
            self.config.cache_file
        ]
        if additional_paths:
            paths.extend(additional_paths)

        for path in paths:
            directory = os.path.dirname(path)
            if directory:
                os.makedirs(directory, exist_ok=True)
                self.logger.debug(f"📁 Ensured directory exists: {directory} for file: {path}")

    def _save_pickle_data(self, path: str, getter_fn: callable, label: str) -> None:
        try:
            with open(path, "wb") as f:
                pickle.dump(getter_fn(), f)
            self.logger.info(f"💾 Saved {label}.")
        except Exception as e:
            self.logger.warning(f"⚠️ Failed to save {label}: {e}")

    def _load_pickle_data(self, path: str, setter_fn: callable = None, label: str = None):
        if not os.path.exists(path):
            self.logger.warning(f"⚠️ Missing file: {path}")
            return None
        try:
            with open(path, "rb") as f:
                data = pickle.load(f)
            if setter_fn:
                setter_fn(data)
            if label:
                self.logger.info(f"   ✅ Loaded {label}.")
            return data
        except Exception as e:
            self.logger.warning(f"⚠️ Failed to load {label or 'pickle'} from {path}: {e}")
            return None
