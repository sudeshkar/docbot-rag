from app.rag.embeddings.base import Embedder
from app.rag.embeddings.cached import CachedEmbedder
from app.rag.embeddings.hashing import HashEmbedder
from app.rag.embeddings.voyage import VoyageEmbedder


def create_embedder(
    provider: str,
    voyage_api_key: str | None = None,
    voyage_model: str = "voyage-3.5",
    cache_size: int = 2048,
) -> Embedder:
    if provider == "voyage":
        inner: Embedder = VoyageEmbedder(api_key=voyage_api_key or "", model=voyage_model)
    elif provider == "hash":
        inner = HashEmbedder()
    else:
        raise ValueError(f"Unknown embedding provider '{provider}'. Options: voyage, hash")
    return CachedEmbedder(inner, max_size=cache_size)
