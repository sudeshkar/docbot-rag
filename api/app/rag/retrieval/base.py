from abc import ABC, abstractmethod
from typing import Protocol
from uuid import UUID

from app.domain.types import RetrievedChunk, ScoredId


class Retriever(ABC):
    """Strategy interface: return up to k chunk ids for a bot, best first."""

    @abstractmethod
    def search(self, bot_id: UUID, query: str, k: int) -> list[ScoredId]: ...


class ChunkReader(Protocol):
    """What retrieval needs from chunk storage (implemented by ChunkRepository)."""

    def keyword_search(self, bot_id: UUID, query: str, k: int) -> list[tuple[str, float]]: ...

    def get_many(self, bot_id: UUID, chunk_ids: list[str]) -> dict[str, RetrievedChunk]: ...
