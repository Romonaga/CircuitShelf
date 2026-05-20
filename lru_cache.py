# lru_cache.py

from collections import OrderedDict

class LRUCache:
    def __init__(self, capacity=200, trace_logger=None):
        self.cache = OrderedDict()
        self.capacity = capacity
        self.hits = 0
        self.misses = 0
        self.trace_logger = trace_logger

    def get(self, key):
        if key not in self.cache:
            self.misses += 1
            if self.trace_logger:
                self.trace_logger.debug(f"Cache MISS for key: {key}")
            return None
        self.cache.move_to_end(key)
        self.hits += 1
        if self.trace_logger:
            self.trace_logger.debug(f"Cache HIT for key: {key}")
        return self.cache[key]

    def put(self, key, value):
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = value
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)

    def stats(self):
        return f"Cache size: {len(self.cache)} / {self.capacity} | Hits: {self.hits} | Misses: {self.misses}"
