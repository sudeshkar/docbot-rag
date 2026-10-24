from uuid import UUID

from app.domain.types import ScoredId
from app.rag.retrieval.base import Retriever
from app.rag.retrieval.fusion import FusionStrategy


class HybridRetriever(Retriever):
    """Composite retriever: asks each child for a wide candidate pool, then fuses down to k."""

    def __init__(self, retrievers: list[Retriever], fusion: FusionStrategy, candidates: int = 20):
        if not retrievers:
            raise ValueError("HybridRetriever needs at least one retriever")
        self.retrievers = retrievers
        self.fusion = fusion
        self.candidates = candidates

    def search(self, bot_id: UUID, query: str, k: int) -> list[ScoredId]:
        pool = max(k, self.candidates)
        rankings = [r.search(bot_id, query, pool) for r in self.retrievers]
        return self.fusion.fuse(rankings, top_n=k)
