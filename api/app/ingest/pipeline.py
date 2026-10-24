import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.domain.types import Section, TextChunk
from app.rag.chunking.base import Chunker
from app.rag.embeddings.base import Embedder
from app.rag.vectorstores.base import VectorStore, namespace_for


@dataclass(frozen=True)
class DocumentRef:
    id: UUID
    bot_id: UUID
    title: str


class ChunkWriter(Protocol):
    def replace_for_document(self, bot_id: UUID, document_id: UUID, chunks: list[TextChunk]) -> list[str]: ...


def contextual_text(title: str, chunk: TextChunk) -> str:
    """Contextual chunk header: prefix the doc title and heading path before embedding, so a chunk
    like "It takes 5 days." is embedded as being about "Help Center > Billing > Refunds"."""
    header = f"{title}\n{chunk.heading}" if chunk.heading else title
    return f"{header}\n\n{chunk.content}"


def dedupe(chunks: list[TextChunk]) -> list[TextChunk]:
    """Drop repeated chunks (nav bars, footers, boilerplate) in one pass with a hash set: O(n)."""
    seen: set[bytes] = set()
    out = []
    for c in chunks:
        key = hashlib.blake2b(" ".join(c.content.lower().split()).encode(), digest_size=16).digest()
        if key not in seen:
            seen.add(key)
            out.append(c)
    return out


class IngestionPipeline:
    """chunk -> dedupe -> persist text -> embed (batched) -> upsert vectors."""

    def __init__(
        self,
        chunker_for: Callable[[str], Chunker],
        embedder: Embedder,
        store: VectorStore,
        chunks: ChunkWriter,
    ):
        self.chunker_for = chunker_for
        self.embedder = embedder
        self.store = store
        self.chunks = chunks

    def index(self, doc: DocumentRef, sections: list[Section], strategy: str) -> int:
        namespace = namespace_for(doc.bot_id)
        # Re-indexing replaces the previous version, so stale vectors never answer questions.
        self.store.delete_document(namespace, str(doc.id))

        chunks = dedupe(self.chunker_for(strategy).chunk(sections))
        ids = self.chunks.replace_for_document(doc.bot_id, doc.id, chunks)
        if not chunks:
            return 0

        embeddings = self.embedder.embed_documents([contextual_text(doc.title, c) for c in chunks])
        self.store.upsert(
            namespace,
            ids=ids,
            embeddings=embeddings,
            documents=[c.content for c in chunks],
            metadatas=[{"document_id": str(doc.id)} for _ in chunks],
        )
        return len(chunks)
