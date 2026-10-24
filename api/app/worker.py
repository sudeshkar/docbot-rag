"""arq worker: runs ingestion off the request path. Start with `arq app.worker.WorkerSettings`."""

import asyncio
import logging
from uuid import UUID

from arq.connections import RedisSettings

from app.container import build_ingestion_service
from app.core.config import get_settings
from app.db.session import SessionLocal

logging.basicConfig(level=logging.INFO)


def _ingest(document_id: UUID) -> None:
    with SessionLocal() as db:
        build_ingestion_service(db).process_document(document_id)


def _crawl(bot_id: UUID, start_url: str, max_pages: int) -> int:
    with SessionLocal() as db:
        return build_ingestion_service(db).crawl_site(bot_id, start_url, max_pages)


async def ingest_document_job(ctx, document_id: str) -> None:
    # Ingestion is CPU/IO-bound sync code; run it in a thread so the event loop stays free.
    await asyncio.to_thread(_ingest, UUID(document_id))


async def crawl_site_job(ctx, bot_id: str, start_url: str, max_pages: int) -> int:
    return await asyncio.to_thread(_crawl, UUID(bot_id), start_url, max_pages)


class WorkerSettings:
    functions = [ingest_document_job, crawl_site_job]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_jobs = 4
    job_timeout = 900
