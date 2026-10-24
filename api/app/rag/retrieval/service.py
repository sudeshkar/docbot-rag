from dataclasses import replace
from uuid import UUID

from app.domain.types import RetrievalResult
from app.rag.retrieval.base import ChunkReader, Retriever


class RetrievalService:
    """Runs a retriever, then hydrates ids into chunks in a single batched query.

    Hydration goes through `get_many(bot_id, ...)`, which only returns the bot's own chunks, so
    even a misrouted vector index can't leak another tenant's text into the prompt.
    """

    def __init__(self, retriever: Retriever, chunks: ChunkReader):
        self.retriever = retriever
        self.chunks = chunks

    def retrieve(self, bot_id: UUID, query: str, top_n: int) -> RetrievalResult:
        hits = self.retriever.search(bot_id, query, top_n)
        if not hits:
            return RetrievalResult()
        rows = self.chunks.get_many(bot_id, [h.chunk_id for h in hits])
        chunks = [
            replace(rows[h.chunk_id], score=h.score, signals=h.signals)
            for h in hits
            if h.chunk_id in rows
        ]
        top_vector = max((h.signals.get("vector", 0.0) for h in hits), default=0.0)
        return RetrievalResult(chunks=chunks, top_vector_score=top_vector)
