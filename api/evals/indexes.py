"""In-memory indexes so the eval harness runs without Postgres/Chroma."""

import heapq
import math
import re
from collections import Counter, defaultdict

TOKEN_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
STOPWORDS = frozenset(
    "a an and are as at be by can do does for from how i if in is it its my of on or the to "
    "what when where which who why will with you your".split()
)


def tokenize(text: str) -> list[str]:
    return [t for t in TOKEN_RE.findall(text.lower()) if t not in STOPWORDS]


class BM25Index:
    """Okapi BM25 over an inverted index (term -> {doc_id: term_freq}).

    A query only touches the postings of its own terms, so cost is proportional to matching
    documents, not corpus size; heapq.nlargest picks top-k in O(m log k).
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.postings: dict[str, dict[str, int]] = defaultdict(dict)
        self.doc_len: dict[str, int] = {}

    def add(self, doc_id: str, text: str) -> None:
        tokens = tokenize(text)
        self.doc_len[doc_id] = len(tokens)
        for term, tf in Counter(tokens).items():
            self.postings[term][doc_id] = tf

    def search(self, query: str, k: int) -> list[tuple[str, float]]:
        n = len(self.doc_len)
        if n == 0:
            return []
        avg_len = sum(self.doc_len.values()) / n
        scores: dict[str, float] = defaultdict(float)
        for term in set(tokenize(query)):
            postings = self.postings.get(term)
            if not postings:
                continue
            idf = math.log(1 + (n - len(postings) + 0.5) / (len(postings) + 0.5))
            for doc_id, tf in postings.items():
                norm = self.k1 * (1 - self.b + self.b * self.doc_len[doc_id] / avg_len)
                scores[doc_id] += idf * tf * (self.k1 + 1) / (tf + norm)
        return heapq.nlargest(k, scores.items(), key=lambda kv: kv[1])


class VectorIndex:
    """Exact (brute-force) cosine search with vectors pre-normalized at insert time.
    O(n·d) per query, fine for an eval corpus; production uses Chroma's HNSW instead."""

    def __init__(self):
        self.ids: list[str] = []
        self.vectors: list[list[float]] = []

    @staticmethod
    def _normalize(v: list[float]) -> list[float]:
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / norm for x in v]

    def add(self, doc_id: str, vector: list[float]) -> None:
        self.ids.append(doc_id)
        self.vectors.append(self._normalize(vector))

    def search(self, query: list[float], k: int) -> list[tuple[str, float]]:
        q = self._normalize(query)
        scored = ((doc_id, sum(a * b for a, b in zip(q, v))) for doc_id, v in zip(self.ids, self.vectors))
        return heapq.nlargest(k, scored, key=lambda kv: kv[1])
