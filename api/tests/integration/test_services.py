from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db.models import Bot, Document, QueryLog, User
from app.domain.types import LoadedDocument, Section
from app.ingest.pipeline import IngestionPipeline
from app.rag.chunking.factory import create_chunker
from app.rag.generation.answer import AnswerGenerator
from app.rag.generation.prompt import PromptBuilder
from app.repositories.chunks import ChunkRepository
from app.services.analytics import AnalyticsService
from app.services.chat import ChatService
from app.services.ingestion import IngestionService
from tests.fakes import FailingLLM, FakeEmbedder, FakeLLM, FakeRetrieval, FakeStore, parse_sse

pytestmark = pytest.mark.integration


@pytest.fixture
def bot(db):
    user = User(email=f"{uuid4().hex}@x.com", password_hash="h")
    db.add(user)
    db.flush()
    bot = Bot(owner_id=user.id, name="Support", public_key=f"pk_{uuid4().hex}", monthly_quota=100)
    db.add(bot)
    db.flush()
    return bot


def chat_service(db, llm=None, retrieval=None):
    return ChatService(db, retrieval or FakeRetrieval(), AnswerGenerator(llm or FakeLLM(), PromptBuilder()))


# --- chat --------------------------------------------------------------------------

def test_chat_streams_events_and_logs_answered_query(db, bot):
    events = parse_sse("".join(chat_service(db).chat_turn(bot, "How long are refunds?", None, "widget")))
    names = [e for e, _ in events]
    assert names[0] == "meta" and names[-2:] == ["sources", "done"]
    assert "".join(d for e, d in events if e == "token").strip() == "Refunds take 5 days [1]."

    sources = dict(events)["sources"]
    assert [s["index"] for s in sources] == [1] and sources[0]["title"] == "Help Center"
    assert dict(events)["done"]["answered"] is True

    log = db.scalar(select(QueryLog).where(QueryLog.bot_id == bot.id))
    assert (log.answered, log.input_tokens, log.cited_document_ids) == (True, 100, ["d1"])


def test_chat_without_citations_is_logged_as_unanswered(db, bot):
    llm = FakeLLM("I couldn't find that in the documentation.")
    events = parse_sse("".join(chat_service(db, llm=llm).chat_turn(bot, "Do you sell boats?", None, "widget")))
    assert dict(events)["done"]["answered"] is False
    assert db.scalar(select(QueryLog.answered).where(QueryLog.bot_id == bot.id)) is False


def test_chat_flags_low_confidence_retrieval(db, bot):
    svc = chat_service(db, retrieval=FakeRetrieval(top_vector_score=0.1))
    events = parse_sse("".join(svc.chat_turn(bot, "q", None, "widget")))
    assert dict(events)["done"]["low_confidence"] is True


def test_chat_continues_conversation_with_history(db, bot):
    llm = FakeLLM()
    svc = chat_service(db, llm=llm)
    first = parse_sse("".join(svc.chat_turn(bot, "first question", None, "widget")))
    conv_id = dict(first)["meta"]["conversation_id"]
    "".join(svc.chat_turn(bot, "follow up", conv_id, "widget"))
    _, messages = llm.calls[-1]
    assert [m["role"] for m in messages] == ["user", "assistant", "user"]
    assert messages[0]["content"] == "first question"


def test_chat_reports_llm_failure_as_error_event(db, bot):
    events = parse_sse("".join(chat_service(db, llm=FailingLLM()).chat_turn(bot, "q", None, "widget")))
    assert events[-1][0] == "error" and "temporarily unavailable" in events[-1][1]["message"]
    assert "done" not in dict(events)


def test_chat_enforces_monthly_quota(db, bot):
    bot.monthly_quota = 1
    db.add(QueryLog(bot_id=bot.id, channel="widget", question="earlier"))
    db.flush()
    events = parse_sse("".join(chat_service(db).chat_turn(bot, "q", None, "widget")))
    assert events[0][0] == "error" and "limit" in events[0][1]["message"]


# --- ingestion ---------------------------------------------------------------------------

class FakeCrawler:
    def __init__(self, pages):
        self.pages = pages

    def crawl(self, url, max_pages):
        return self.pages[:max_pages]

    def fetch_one(self, url):
        return self.pages[0] if self.pages else None


def ingestion_service(db, crawler=None, store=None):
    store = store or FakeStore()
    pipeline = IngestionPipeline(lambda s: create_chunker(s, 200, 20), FakeEmbedder(), store, ChunkRepository(db))
    return IngestionService(db, pipeline, crawler or FakeCrawler([]))


def test_ingest_uploaded_file_marks_ready(db, bot, tmp_path: Path):
    f = tmp_path / "faq.md"
    f.write_text("# Refunds\nRefunds take 5 days.\n# Shipping\nShips in a week.", encoding="utf-8")
    doc = Document(bot_id=bot.id, title="faq.md", source_type="file", file_path=str(f))
    db.add(doc)
    db.flush()
    ingestion_service(db).process_document(doc.id)
    db.refresh(doc)
    assert (doc.status, doc.chunk_count, doc.error) == ("ready", 2, None)


def test_ingest_failure_is_recorded_on_document(db, bot, tmp_path: Path):
    doc = Document(bot_id=bot.id, title="gone.md", source_type="file", file_path=str(tmp_path / "missing.md"))
    db.add(doc)
    db.flush()
    ingestion_service(db).process_document(doc.id)
    db.refresh(doc)
    assert doc.status == "failed" and doc.error


def test_crawl_creates_a_ready_document_per_page(db, bot):
    pages = [
        LoadedDocument("Home", [Section("Welcome to Acme support.")], "https://acme.test"),
        LoadedDocument("Refunds", [Section("Refunds take 5 days.")], "https://acme.test/refunds"),
    ]
    count = ingestion_service(db, crawler=FakeCrawler(pages)).crawl_site(bot.id, "https://acme.test", 10)
    docs = db.scalars(select(Document).where(Document.bot_id == bot.id).order_by(Document.title)).all()
    assert count == 2
    assert [(d.title, d.status, d.source_url) for d in docs] == [
        ("Home", "ready", "https://acme.test"),
        ("Refunds", "ready", "https://acme.test/refunds"),
    ]


# --- analytics ----------------------------------------------------------------------------

def test_analytics_overview(db, bot):
    now = datetime.now(timezone.utc)
    db.add_all([
        QueryLog(bot_id=bot.id, channel="widget", question="Refunds?", answered=True, latency_ms=100,
                 cited_document_ids=["d1"], input_tokens=10, output_tokens=5),
        QueryLog(bot_id=bot.id, channel="widget", question="Do you sell boats?", answered=False, latency_ms=300),
        QueryLog(bot_id=bot.id, channel="widget", question="do you sell  BOATS?", answered=False, latency_ms=200),
        QueryLog(bot_id=bot.id, channel="widget", question="ancient", answered=False,
                 created_at=now - timedelta(days=60)),
    ])
    db.flush()
    o = AnalyticsService(db).overview(bot.id, days=30)
    assert o["total_queries"] == 3
    assert o["answer_rate"] == pytest.approx(1 / 3)
    assert o["avg_latency_ms"] == 200
    assert len(o["daily"]) == 30 and o["daily"][-1]["queries"] == 3
    assert o["unanswered"][0] == {"question": "do you sell boats", "count": 2}
    assert o["top_documents"] == [{"document_id": "d1", "title": None, "citations": 1}]


def test_unanswered_grouping_ignores_trailing_punctuation(db, bot):
    for q in ["Do you have a mobile app?", "do you have a mobile app", "Do you have a mobile app?!"]:
        db.add(QueryLog(bot_id=bot.id, channel="widget", question=q, answered=False))
    db.flush()
    assert AnalyticsService(db).overview(bot.id)["unanswered"] == [
        {"question": "do you have a mobile app", "count": 3}
    ]
