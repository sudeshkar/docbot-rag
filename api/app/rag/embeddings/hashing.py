import hashlib
import math
import re

from app.rag.embeddings.base import Embedder

TOKEN_RE = re.compile(r"[a-z0-9]+")


class HashEmbedder(Embedder):
    """Offline dev fallback: signed feature hashing of unigrams + bigrams into a fixed-size vector.
    O(tokens) per text, no network, no model download. Retrieval quality is far below a real model."""

    def __init__(self, dim: int = 512):
        self.dim = dim

    def _embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        words = TOKEN_RE.findall(text.lower())
        for token in words + [f"{a}_{b}" for a, b in zip(words, words[1:])]:
            h = int.from_bytes(hashlib.blake2b(token.encode(), digest_size=8).digest(), "little")
            vec[h % self.dim] += 1.0 if (h >> 63) & 1 else -1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)
