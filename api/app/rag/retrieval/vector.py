from uuid import UUID

from app.domain.types import ScoredId
from app.rag.embeddings.base import Embedder
from app.rag.retrieval.base import Retriever
from app.rag.vectorstores.base import VectorStore, namespace_for


class VectorRetriever(Retriever):
    """Dense retrieval: embed the query, ANN search (HNSW in Chroma, ~O(log n)) in the bot's namespace."""

    def __init__(self, embedder: Embedder, store: VectorStore):
        self.embedder = embedder
        self.store = store

    def search(self, bot_id: UUID, query: str, k: int) -> list[ScoredId]:
        hits = self.store.query(namespace_for(bot_id), self.embedder.embed_query(query), k)
        return [ScoredId(h.chunk_id, h.score, {"vector": h.score}) for h in hits]
