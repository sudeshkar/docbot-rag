import heapq
from abc import ABC, abstractmethod

from app.domain.types import ScoredId


class FusionStrategy(ABC):
    @abstractmethod
    def fuse(self, rankings: list[list[ScoredId]], top_n: int) -> list[ScoredId]: ...


class ReciprocalRankFusion(FusionStrategy):
    """score(d) = sum over rankings of 1 / (k + rank_d).

    Uses ranks, not raw scores, so cosine similarities and BM25-style scores (different scales)
    combine without normalization. One hash-map pass is O(N) over all hits; selecting the best
    top_n with a heap is O(N log top_n) instead of sorting everything.
    """

    def __init__(self, k: int = 60):
        self.k = k

    def fuse(self, rankings: list[list[ScoredId]], top_n: int) -> list[ScoredId]:
        scores: dict[str, float] = {}
        signals: dict[str, dict[str, float]] = {}
        first_seen: dict[str, int] = {}
        for ranking in rankings:
            for rank, hit in enumerate(ranking, start=1):
                cid = hit.chunk_id
                if cid not in scores:
                    first_seen[cid] = len(first_seen)
                    scores[cid] = 0.0
                    signals[cid] = {}
                scores[cid] += 1.0 / (self.k + rank)
                signals[cid].update(hit.signals)

        # Ties broken by first appearance so results are deterministic.
        best = heapq.nlargest(top_n, scores, key=lambda cid: (scores[cid], -first_seen[cid]))
        return [ScoredId(cid, scores[cid], signals[cid]) for cid in best]
