# state_manager.py

"""
@authors: sueco, rew
"""

import threading
from collections import deque
from response_cache import ResponseCache

class StateManager:
    def __init__(self, use_lock=True, cache_capacity=200, trace_logger=None):
        self.use_lock = use_lock
        self.lock = threading.Lock() if use_lock else None

        # === Core State ===
        self.chunks = []
        self.sources = []
        self.chunk_metadata = []
        self.embeddings = []
        self.index = None

        # === Image State ===
        self.image_store = {}
        self.image_captions = {}
        self.image_page_text = {}
        self.image_mime_types = {}
        self.image_id_list = []

        # === Query/Debug State ===
        self.query_timings = deque(maxlen=100)
        self.last_trace_data = {}
    

        # === Cache ===
        self.cache = ResponseCache(capacity=cache_capacity, trace_logger=trace_logger)

    def get_cache(self):
        return self.cache

    def set_cache(self, cache):
        self.cache = cache

    # === Chunk Data ===
    def get_chunks(self): return self._safe(lambda: list(self.chunks))
    def set_chunks(self, data): self._safe(lambda: self._replace(self.chunks, data))
    def extend_chunks(self, chunks, sources, meta):
        def _extend():
            self.chunks.extend(chunks)
            self.sources.extend(sources)
            self.chunk_metadata.extend(meta)
        self._safe(_extend)

    def get_sources(self): return self._safe(lambda: list(self.sources))
    def set_sources(self, data): self._safe(lambda: self._replace(self.sources, data))

    def get_metadata(self): return self._safe(lambda: list(self.chunk_metadata))
    def set_metadata(self, data): self._safe(lambda: self._replace(self.chunk_metadata, data))

    def clear_all(self):
        def _clear():
            self.chunks.clear()
            self.sources.clear()
            self.chunk_metadata.clear()
            self.embeddings.clear()
            self.image_store.clear()
            self.image_captions.clear()
            self.image_page_text.clear()
            self.image_mime_types.clear()
            self.image_id_list.clear()
            self.last_trace_data.clear()
            self.index = None
        self._safe(_clear)

    def replace_catalog(
        self,
        *,
        chunks,
        sources,
        metadata,
        embeddings,
        image_store=None,
        image_captions=None,
        image_page_text=None,
        image_mime_types=None,
        image_id_list=None,
        index=None,
    ):
        def _replace_catalog():
            self._replace(self.chunks, chunks)
            self._replace(self.sources, sources)
            self._replace(self.chunk_metadata, metadata)
            self._replace(self.embeddings, embeddings)
            if image_store is not None:
                self._replace(self.image_store, image_store)
            if image_captions is not None:
                self._replace(self.image_captions, image_captions)
            if image_page_text is not None:
                self._replace(self.image_page_text, image_page_text)
            if image_mime_types is not None:
                self._replace(self.image_mime_types, image_mime_types)
            if image_id_list is not None:
                self._replace(self.image_id_list, image_id_list)
            self.index = index

        self._safe(_replace_catalog)

    # === Embeddings ===
    def get_embeddings(self): return self._safe(lambda: list(self.embeddings))
    def set_embeddings(self, data): self._safe(lambda: self._replace(self.embeddings, data))
    def add_embedding(self, emb): self._safe(lambda: self.embeddings.append(emb))


    # === Index ===
    def get_index(self): return self._safe(lambda: self.index)
    def set_index(self, index): self._safe(lambda: self._set_attr("index", index))
    

    # === Image Data ===
    def get_image_store(self): return self._safe(lambda: dict(self.image_store))
    def set_image_store(self, store): self._safe(lambda: self._replace(self.image_store, store))
    def add_image_store(self, key, value):
        self._safe(lambda: self.image_store.__setitem__(key, value))


     # === Image Captions ===
    def get_image_captions(self): return self._safe(lambda: dict(self.image_captions))
    def set_image_captions(self, data): self._safe(lambda: self._replace(self.image_captions, data))
    def add_image_caption(self, key, value):
        self._safe(lambda: self.image_captions.__setitem__(key, value))

    # === Image Page Text ===
    def get_image_page_text(self): return self._safe(lambda: dict(self.image_page_text))
    def set_image_page_text(self, data): self._safe(lambda: self._replace(self.image_page_text, data))
    def add_image_page_text(self, key, value):
        self._safe(lambda: self.image_page_text.__setitem__(key, value))

    # === Image MIME Types ===
    def get_image_mime_types(self): return self._safe(lambda: dict(self.image_mime_types))
    def set_image_mime_types(self, data): self._safe(lambda: self._replace(self.image_mime_types, data))
    def add_image_mime_type(self, key, value):
        self._safe(lambda: self.image_mime_types.__setitem__(key, value))

    # === Image ID List ===
    def get_image_id_list(self): return self._safe(lambda: list(self.image_id_list))
    def set_image_id_list(self, ids): self._safe(lambda: self._replace(self.image_id_list, ids))
    def add_image_id(self, img_id):
        self._safe(lambda: self.image_id_list.append(img_id))



    # === Trace / Debug ===
    def get_query_timings(self): return self._safe(lambda: list(self.query_timings))
    def append_query_time(self, t): self._safe(lambda: self.query_timings.append(t))

    def get_last_trace(self): return self._safe(lambda: dict(self.last_trace_data))
    def update_last_trace(self, data): self._safe(lambda: self._replace(self.last_trace_data, data))


    def count_embeddings_for_source(self, src):
        return self._safe(lambda: sum(1 for s in self.sources if s == src))

    def count_images_for_source(self, src):
        return self._safe(lambda: sum(1 for img_id in self.image_id_list if src in img_id))

    

    # === Internals ===
    def _replace(self, target, data):
        if isinstance(target, (list, deque)):
            target.clear()
            target.extend(data)
        elif isinstance(target, dict):
            target.clear()
            target.update(data)

    def _set_attr(self, attr, value):
        setattr(self, attr, value)

    def _safe(self, func, *args, **kwargs):
        if self.use_lock:
            with self.lock:
                return func(*args, **kwargs)
        return func(*args, **kwargs)
    
