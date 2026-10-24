from abc import ABC, abstractmethod
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class VectorHit:
    chunk_id: str
    score: float  # cosine similarity, higher is better


def namespace_for(bot_id: UUID) -> str:
    """One namespace (Chroma collection) per bot: tenant isolation at the index level."""
    return f"bot_{bot_id.hex}"


class VectorStore(ABC):
    """Port for vector databases. Chroma is the adapter today; pgvector/Qdrant could slot in."""

    @abstractmethod
    def upsert(
        self,
        namespace: str,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict],
    ) -> None: ...

    @abstractmethod
    def query(self, namespace: str, embedding: list[float], k: int) -> list[VectorHit]: ...

    @abstractmethod
    def delete_document(self, namespace: str, document_id: str) -> None: ...

    @abstractmethod
    def drop_namespace(self, namespace: str) -> None: ...

    @abstractmethod
    def ping(self) -> bool: ...
