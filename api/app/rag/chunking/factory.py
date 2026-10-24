"""Factory for chunkers. Importing the strategy modules registers them."""

from app.rag.chunking import fixed, markdown, recursive, semantic  # noqa: F401  (registration side effect)
from app.rag.chunking.base import Chunker
from app.rag.chunking.registry import CHUNKERS
from app.rag.embeddings.base import Embedder

__all__ = ["CHUNKERS", "available_strategies", "create_chunker"]

DEFAULT_STRATEGY = "markdown"


def available_strategies() -> list[dict]:
    return [{"name": name, "description": cls.description} for name, cls in CHUNKERS.items()]


def create_chunker(
    name: str, max_tokens: int, overlap_tokens: int, embedder: Embedder | None = None
) -> Chunker:
    cls = CHUNKERS.get(name)
    if cls is None:
        raise ValueError(f"Unknown chunking strategy '{name}'. Options: {sorted(CHUNKERS)}")
    if getattr(cls, "requires_embedder", False):
        if embedder is None:
            raise ValueError(f"Chunker '{name}' needs an embedder")
        return cls(embedder=embedder, max_tokens=max_tokens, overlap_tokens=overlap_tokens)
    return cls(max_tokens=max_tokens, overlap_tokens=overlap_tokens)
