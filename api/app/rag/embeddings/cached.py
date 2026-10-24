import threading
from collections import OrderedDict

from app.rag.embeddings.base import Embedder


class CachedEmbedder(Embedder):
    """Decorator that memoizes query embeddings in an LRU cache.

    Support questions repeat a lot ("how do I reset my password"), so a hit skips a ~100ms network
    call. OrderedDict gives O(1) lookup, O(1) move-to-end on hit and O(1) eviction of the oldest entry.
    Documents are not cached: each one is embedded once at ingest time.
    """

    def __init__(self, inner: Embedder, max_size: int = 2048):
        self.inner = inner
        self.max_size = max_size
        self._cache: OrderedDict[str, tuple[float, ...]] = OrderedDict()
        self._lock = threading.Lock()  # FastAPI runs sync endpoints on a thread pool

    @staticmethod
    def _key(text: str) -> str:
        return " ".join(text.lower().split())

    def embed_query(self, text: str) -> list[float]:
        key = self._key(text)
        with self._lock:
            hit = self._cache.get(key)
            if hit is not None:
                self._cache.move_to_end(key)
                return list(hit)
        vector = self.inner.embed_query(text)
        with self._lock:
            # Stored as an immutable tuple and copied on read, so callers can't mutate the cache.
            self._cache[key] = tuple(vector)
            self._cache.move_to_end(key)
            if len(self._cache) > self.max_size:
                self._cache.popitem(last=False)
        return list(vector)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.inner.embed_documents(texts)
