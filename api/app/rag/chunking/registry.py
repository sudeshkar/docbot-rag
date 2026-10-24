"""Registry of chunking strategies, populated by the @register_chunker decorator on each class."""

from app.rag.chunking.base import Chunker

CHUNKERS: dict[str, type[Chunker]] = {}


def register_chunker(cls: type[Chunker]) -> type[Chunker]:
    if cls.name in CHUNKERS:
        raise ValueError(f"Duplicate chunker name: {cls.name}")
    CHUNKERS[cls.name] = cls
    return cls
