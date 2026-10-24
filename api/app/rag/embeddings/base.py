from abc import ABC, abstractmethod


class Embedder(ABC):
    """Strategy interface for embedding providers. Documents and queries are separate calls because
    retrieval-tuned models (e.g. Voyage) embed them asymmetrically."""

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    @abstractmethod
    def embed_query(self, text: str) -> list[float]: ...
