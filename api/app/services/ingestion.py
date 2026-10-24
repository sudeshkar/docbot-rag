import logging
from pathlib import Path
from typing import Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import Bot, Document
from app.domain.types import LoadedDocument
from app.ingest.loaders.registry import load_file
from app.ingest.pipeline import DocumentRef, IngestionPipeline

log = logging.getLogger(__name__)


class Crawler(Protocol):
    def crawl(self, start_url: str, max_pages: int) -> list[LoadedDocument]: ...
    def fetch_one(self, url: str) -> LoadedDocument | None: ...


class IngestionService:
    def __init__(self, db: Session, pipeline: IngestionPipeline, crawler: Crawler):
        self.db = db
        self.pipeline = pipeline
        self.crawler = crawler

    def _strategy(self, bot_id: UUID) -> str:
        bot = self.db.get(Bot, bot_id)
        return bot.chunking_strategy if bot else "markdown"

    def process_document(self, document_id: UUID) -> None:
        doc = self.db.get(Document, document_id)
        if doc is None:
            return
        doc.status, doc.error = "processing", None
        self.db.commit()
        try:
            # A savepoint per document: a failure undoes only this document's partial writes.
            with self.db.begin_nested():
                if doc.source_type == "file":
                    loaded = load_file(Path(doc.file_path), doc.title)
                else:
                    loaded = self.crawler.fetch_one(doc.source_url)
                    if loaded is None:
                        raise ValueError("Could not fetch readable HTML from that URL")
                    doc.title = loaded.title
                doc.chunk_count = self.pipeline.index(
                    DocumentRef(doc.id, doc.bot_id, doc.title), loaded.sections, self._strategy(doc.bot_id)
                )
                if doc.chunk_count == 0:
                    raise ValueError("No text could be extracted from this document")
            doc.status = "ready"
        except Exception as exc:  # any failure is shown to the user on the document row
            log.exception("ingest failed for document %s", document_id)
            self.db.refresh(doc)
            doc.status, doc.error, doc.chunk_count = "failed", str(exc)[:1000], 0
        self.db.commit()

    def crawl_site(self, bot_id: UUID, start_url: str, max_pages: int) -> int:
        strategy = self._strategy(bot_id)
        indexed = 0
        for page in self.crawler.crawl(start_url, max_pages):
            doc = Document(bot_id=bot_id, title=page.title, source_type="url",
                           source_url=page.source_url, status="processing")
            self.db.add(doc)
            self.db.flush()
            try:
                with self.db.begin_nested():
                    doc.chunk_count = self.pipeline.index(
                        DocumentRef(doc.id, bot_id, doc.title), page.sections, strategy
                    )
                doc.status = "ready" if doc.chunk_count else "failed"
                doc.error = None if doc.chunk_count else "No text found on page"
                indexed += 1 if doc.chunk_count else 0
            except Exception as exc:
                log.exception("indexing %s failed", page.source_url)
                doc.status, doc.error = "failed", str(exc)[:1000]
            self.db.commit()
        return indexed
