from uuid import UUID

from app.domain.types import ScoredId
from app.rag.retrieval.base import ChunkReader, Retriever


class KeywordRetriever(Retriever):
    """Lexical retrieval via Postgres full-text search (GIN index). Catches exact terms that
    embeddings blur: error codes, product names, SKUs."""

    def __init__(self, chunks: ChunkReader):
        self.chunks = chunks

    def search(self, bot_id: UUID, query: str, k: int) -> list[ScoredId]:
        return [
            ScoredId(cid, score, {"keyword": score})
            for cid, score in self.chunks.keyword_search(bot_id, query, k)
        ]
