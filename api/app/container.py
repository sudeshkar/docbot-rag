"""Composition root: the one place that wires concrete adapters into services.

Long-lived, thread-safe adapters (HTTP clients, caches) are process singletons via lru_cache.
Anything holding a DB session is built per request. Each provider is a FastAPI dependency, so
tests swap any of them with `app.dependency_overrides`.
"""

from collections.abc import Callable
from functools import lru_cache
from uuid import UUID

import redis
from arq import create_pool
from arq.connections import ArqRedis, RedisSettings
from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.ingest.loaders.web import SiteCrawler
from app.ingest.pipeline import IngestionPipeline
from app.ingest.url_safety import assert_public_url
from app.rag.chunking.factory import create_chunker
from app.rag.embeddings.base import Embedder
from app.rag.embeddings.factory import create_embedder
from app.rag.generation.answer import AnswerGenerator
from app.rag.generation.factory import create_llm
from app.rag.generation.llm import LLM
from app.rag.generation.prompt import PromptBuilder
from app.rag.retrieval.fusion import ReciprocalRankFusion
from app.rag.retrieval.hybrid import HybridRetriever
from app.rag.retrieval.keyword import KeywordRetriever
from app.rag.retrieval.service import RetrievalService
from app.rag.retrieval.vector import VectorRetriever
from app.rag.vectorstores.base import VectorStore
from app.rag.vectorstores.chroma import ChromaVectorStore
from app.repositories.chunks import ChunkRepository
from app.services.chat import ChatService
from app.services.ingestion import IngestionService
from app.services.rate_limit import RateLimiter, RedisRateLimiter


# --- singletons --------------------------------------------------------------------

@lru_cache
def get_embedder() -> Embedder:
    s = get_settings()
    return create_embedder(s.embedding_provider, s.voyage_api_key, s.voyage_model)


@lru_cache
def get_vector_store() -> VectorStore:
    s = get_settings()
    return ChromaVectorStore(s.chroma_host, s.chroma_port)


@lru_cache
def get_llm() -> LLM:
    s = get_settings()
    return create_llm(
        s.llm_provider,
        anthropic_api_key=s.anthropic_api_key,
        llm_model=s.llm_model,
        llm_effort=s.llm_effort,
        llm_fallbacks=s.llm_fallbacks,
        groq_api_key=s.groq_api_key,
        groq_model=s.groq_model,
    )


@lru_cache
def get_rate_limiter() -> RateLimiter:
    s = get_settings()
    return RedisRateLimiter(redis.Redis.from_url(s.redis_url), secret=s.jwt_secret)


def get_url_guard() -> Callable[[str], None]:
    return assert_public_url


class ArqJobQueue:
    """Hands slow work (parsing, embedding, crawling) to the arq worker so requests return fast."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._pool: ArqRedis | None = None

    async def _get_pool(self) -> ArqRedis:
        if self._pool is None:
            self._pool = await create_pool(RedisSettings.from_dsn(self.settings.redis_url))
        return self._pool

    async def enqueue_ingest(self, document_id: UUID) -> None:
        await (await self._get_pool()).enqueue_job("ingest_document_job", str(document_id))

    async def enqueue_crawl(self, bot_id: UUID, url: str, max_pages: int) -> None:
        await (await self._get_pool()).enqueue_job("crawl_site_job", str(bot_id), url, max_pages)


@lru_cache
def get_job_queue() -> ArqJobQueue:
    return ArqJobQueue(get_settings())


# --- per-request / per-job builders ----------------------------------------------------

def build_retrieval(db: Session, embedder: Embedder, store: VectorStore, settings: Settings) -> RetrievalService:
    chunks = ChunkRepository(db)
    hybrid = HybridRetriever(
        [VectorRetriever(embedder, store), KeywordRetriever(chunks)],
        ReciprocalRankFusion(),
        candidates=settings.retrieve_k,
    )
    return RetrievalService(hybrid, chunks)


def get_chat_service(
    db: Session = Depends(get_db),
    embedder: Embedder = Depends(get_embedder),
    store: VectorStore = Depends(get_vector_store),
    llm: LLM = Depends(get_llm),
) -> ChatService:
    s = get_settings()
    return ChatService(
        db,
        build_retrieval(db, embedder, store, s),
        AnswerGenerator(llm, PromptBuilder()),
        context_k=s.context_k,
        low_confidence_score=s.low_confidence_score,
    )


def build_ingestion_service(db: Session) -> IngestionService:
    s = get_settings()
    embedder = get_embedder()
    pipeline = IngestionPipeline(
        lambda strategy: create_chunker(strategy, s.chunk_tokens, s.chunk_overlap, embedder),
        embedder,
        get_vector_store(),
        ChunkRepository(db),
    )
    return IngestionService(db, pipeline, SiteCrawler())
