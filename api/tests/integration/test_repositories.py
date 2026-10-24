from datetime import datetime, timedelta, timezone

import pytest

from app.db.models import Bot, Document, QueryLog, User
from app.domain.types import TextChunk
from app.repositories.bots import BotRepository
from app.repositories.chunks import ChunkRepository
from app.repositories.conversations import ConversationRepository
from app.repositories.query_logs import QueryLogRepository
from app.repositories.users import UserRepository

pytestmark = pytest.mark.integration


def make_user(db, email="owner@example.com"):
    return UserRepository(db).add(email, "hash")


def make_bot(db, owner, name="Bot"):
    bot = Bot(owner_id=owner.id, name=name, public_key=f"pk_{name}_{owner.id.hex[:6]}")
    db.add(bot)
    db.flush()
    return bot


def make_doc(db, bot, title="Doc"):
    doc = Document(bot_id=bot.id, title=title, source_type="file", status="ready")
    db.add(doc)
    db.flush()
    return doc


# --- users ----------------------------------------------------------------------

def test_user_lookup_is_case_insensitive(db):
    make_user(db, "Alice@Example.com")
    repo = UserRepository(db)
    assert repo.get_by_email("alice@example.COM") is not None
    assert repo.get_by_email("bob@example.com") is None


# --- bots: ownership ---------------------------------------------------------------

def test_get_for_owner_hides_other_users_bots(db):
    alice, mallory = make_user(db, "a@x.com"), make_user(db, "m@x.com")
    bot = make_bot(db, alice)
    repo = BotRepository(db)
    assert repo.get_for_owner(alice.id, bot.id).id == bot.id
    assert repo.get_for_owner(mallory.id, bot.id) is None


def test_list_for_owner_includes_counts_in_one_query(db):
    owner = make_user(db)
    bot = make_bot(db, owner)
    make_doc(db, bot)
    make_doc(db, bot)
    db.add(QueryLog(bot_id=bot.id, channel="widget", question="q"))
    db.flush()
    summaries = BotRepository(db).list_for_owner(owner.id)
    assert [(s.bot.id, s.document_count, s.queries_this_month) for s in summaries] == [(bot.id, 2, 1)]


# --- chunks: tenant isolation + keyword search -------------------------------------------

def test_keyword_search_ranks_matches_and_isolates_tenants(db):
    owner = make_user(db)
    bot_a, bot_b = make_bot(db, owner, "A"), make_bot(db, owner, "B")
    doc_a, doc_b = make_doc(db, bot_a), make_doc(db, bot_b)
    repo = ChunkRepository(db)
    ids_a = repo.replace_for_document(bot_a.id, doc_a.id, [
        TextChunk("Refunds are processed within 5 business days.", "Billing > Refunds"),
        TextChunk("Shipping takes a week.", "Shipping"),
    ])
    repo.replace_for_document(bot_b.id, doc_b.id, [TextChunk("Refunds are never given.", None)])

    hits = [cid for cid, _ in repo.keyword_search(bot_a.id, "how long do refunds take", k=5)]
    assert hits[0] == ids_a[0]  # matches more query terms -> ranked first (OR semantics)
    assert set(hits) <= set(ids_a)

    # bot B's refund chunk exists but must never surface for bot A, even when asked for by id
    b_ids = [cid for cid, _ in repo.keyword_search(bot_b.id, "refunds", k=5)]
    assert b_ids and not set(b_ids) & set(hits)
    assert repo.get_many(bot_a.id, b_ids + ids_a) .keys() == set(ids_a)


def test_keyword_search_survives_hostile_query_syntax(db):
    owner = make_user(db)
    bot = make_bot(db, owner)
    doc = make_doc(db, bot)
    ChunkRepository(db).replace_for_document(bot.id, doc.id, [TextChunk("plain text", None)])
    for q in ["'; DROP TABLE chunks; --", "a & | ! ( ) :*", "", "   "]:
        ChunkRepository(db).keyword_search(bot.id, q, k=5)  # must not raise


def test_replace_for_document_replaces_previous_chunks(db):
    owner = make_user(db)
    bot = make_bot(db, owner)
    doc = make_doc(db, bot)
    repo = ChunkRepository(db)
    repo.replace_for_document(bot.id, doc.id, [TextChunk("old version", None)])
    new_ids = repo.replace_for_document(bot.id, doc.id, [TextChunk("new version", None)])
    assert repo.keyword_search(bot.id, "old", k=5) == []
    assert [c for c, _ in repo.keyword_search(bot.id, "new", k=5)] == new_ids


def test_get_many_hydrates_document_fields(db):
    owner = make_user(db)
    bot = make_bot(db, owner)
    doc = make_doc(db, bot, title="Help Center")
    [cid] = ChunkRepository(db).replace_for_document(bot.id, doc.id, [TextChunk("body", "H", {"page": 4})])
    chunk = ChunkRepository(db).get_many(bot.id, [cid])[cid]
    assert (chunk.document_title, chunk.heading, chunk.content, chunk.meta) == ("Help Center", "H", "body", {"page": 4})


# --- conversations -------------------------------------------------------------------

def test_conversation_cannot_be_hijacked_across_bots(db):
    owner = make_user(db)
    bot_a, bot_b = make_bot(db, owner, "A"), make_bot(db, owner, "B")
    repo = ConversationRepository(db)
    conv_a = repo.get_or_create(bot_a.id, None, "widget")
    conv = repo.get_or_create(bot_b.id, conv_a.id, "widget")
    assert conv.id != conv_a.id and conv.bot_id == bot_b.id


def test_recent_messages_returns_last_n_in_order(db):
    owner = make_user(db)
    bot = make_bot(db, owner)
    repo = ConversationRepository(db)
    conv = repo.get_or_create(bot.id, None, "playground")
    for i in range(5):
        repo.add_turn(conv.id, f"q{i}", f"a{i}", sources=[])
    assert [m["content"] for m in repo.recent_messages(conv.id, limit=4)] == ["q3", "a3", "q4", "a4"]


# --- query logs ------------------------------------------------------------------------

def test_count_since_only_counts_window(db):
    owner = make_user(db)
    bot = make_bot(db, owner)
    old = datetime.now(timezone.utc) - timedelta(days=40)
    db.add_all([
        QueryLog(bot_id=bot.id, channel="widget", question="new"),
        QueryLog(bot_id=bot.id, channel="widget", question="old", created_at=old),
    ])
    db.flush()
    since = datetime.now(timezone.utc) - timedelta(days=30)
    assert QueryLogRepository(db).count_since(bot.id, since) == 1
