from uuid import uuid4

import pytest

from app.domain.types import RetrievedChunk, ScoredId
from app.rag.retrieval.base import Retriever
from app.rag.retrieval.fusion import ReciprocalRankFusion
from app.rag.retrieval.hybrid import HybridRetriever
from app.rag.retrieval.keyword import KeywordRetriever
from app.rag.retrieval.service import RetrievalService
from app.rag.retrieval.vector import VectorRetriever
from app.rag.vectorstores.base import VectorHit

BOT = uuid4()
OTHER_BOT = uuid4()


def ids(hits):
    return [h.chunk_id for h in hits]


# --- fakes ------------------------------------------------------------------------

class StaticRetriever(Retriever):
    def __init__(self, name, ranked, scores=None):
        self.name = name
        self.ranked = ranked
        self.scores = scores or {}
        self.calls = []

    def search(self, bot_id, query, k):
        self.calls.append((bot_id, query, k))
        return [ScoredId(cid, self.scores.get(cid, 1.0), {self.name: self.scores.get(cid, 1.0)})
                for cid in self.ranked[:k]]


class FakeStore:
    def __init__(self, hits):
        self.hits = hits
        self.queried = []

    def query(self, namespace, embedding, k):
        self.queried.append((namespace, embedding, k))
        return self.hits[:k]


class FakeEmbedder:
    def embed_query(self, text):
        return [0.1, 0.2]

    def embed_documents(self, texts):
        return [[0.1, 0.2] for _ in texts]


class FakeChunkRepo:
    """Holds chunks per bot; get_many only returns chunks owned by the requested bot (like the SQL)."""

    def __init__(self, by_bot):
        self.by_bot = by_bot
        self.keyword_calls = []

    def keyword_search(self, bot_id, query, k):
        self.keyword_calls.append((bot_id, query, k))
        return [("k1", 0.9), ("k2", 0.4)][:k]

    def get_many(self, bot_id, chunk_ids):
        owned = self.by_bot.get(bot_id, {})
        return {cid: owned[cid] for cid in chunk_ids if cid in owned}


def chunk(cid, doc="d1"):
    return RetrievedChunk(cid, doc, "Doc", None, None, f"content {cid}", {}, 0.0)


# --- fusion -------------------------------------------------------------------------

def test_rrf_rewards_items_found_by_both_retrievers():
    vector = [ScoredId("a", 0.9, {"vector": 0.9}), ScoredId("b", 0.8, {"vector": 0.8})]
    keyword = [ScoredId("c", 5.0, {"keyword": 5.0}), ScoredId("b", 3.0, {"keyword": 3.0})]
    fused = ReciprocalRankFusion(k=60).fuse([vector, keyword], top_n=3)
    assert ids(fused) == ["b", "a", "c"]
    b = fused[0]
    assert b.score == pytest.approx(1 / 62 + 1 / 62)
    assert b.signals == {"vector": 0.8, "keyword": 3.0}


def test_rrf_top_n_and_empty_input():
    fusion = ReciprocalRankFusion()
    assert fusion.fuse([], top_n=5) == []
    many = [ScoredId(str(i), 1.0) for i in range(100)]
    assert ids(fusion.fuse([many], top_n=3)) == ["0", "1", "2"]


def test_rrf_is_deterministic_on_ties():
    fused = ReciprocalRankFusion().fuse([[ScoredId("x", 1)], [ScoredId("y", 1)]], top_n=2)
    assert ids(fused) == ["x", "y"]


# --- vector / keyword retrievers ------------------------------------------------------

def test_vector_retriever_queries_the_bots_namespace():
    store = FakeStore([VectorHit("a", 0.91), VectorHit("b", 0.5)])
    hits = VectorRetriever(FakeEmbedder(), store).search(BOT, "q", k=5)
    assert store.queried == [(f"bot_{BOT.hex}", [0.1, 0.2], 5)]
    assert ids(hits) == ["a", "b"]
    assert hits[0].signals == {"vector": 0.91}


def test_keyword_retriever_delegates_to_repo():
    repo = FakeChunkRepo({})
    hits = KeywordRetriever(repo).search(BOT, "refund", k=1)
    assert repo.keyword_calls == [(BOT, "refund", 1)]
    assert ids(hits) == ["k1"] and hits[0].signals == {"keyword": 0.9}


# --- hybrid composite ----------------------------------------------------------------

def test_hybrid_composes_retrievers_with_fusion():
    v = StaticRetriever("vector", ["a", "b"])
    k = StaticRetriever("keyword", ["b", "c"])
    hybrid = HybridRetriever([v, k], ReciprocalRankFusion(), candidates=20)
    hits = hybrid.search(BOT, "q", k=2)
    assert ids(hits) == ["b", "a"]
    assert v.calls == [(BOT, "q", 20)] and k.calls == [(BOT, "q", 20)]


def test_hybrid_requires_retrievers():
    with pytest.raises(ValueError):
        HybridRetriever([], ReciprocalRankFusion())


# --- service ----------------------------------------------------------------------

def test_service_hydrates_in_rank_order_and_reports_top_vector_score():
    repo = FakeChunkRepo({BOT: {"a": chunk("a"), "b": chunk("b")}})
    retriever = StaticRetriever("vector", ["b", "a"], scores={"a": 0.3, "b": 0.7})
    result = RetrievalService(retriever, repo).retrieve(BOT, "q", top_n=5)
    assert [c.chunk_id for c in result.chunks] == ["b", "a"]
    assert result.top_vector_score == pytest.approx(0.7)
    assert result.chunks[0].score == pytest.approx(0.7)


def test_service_drops_chunks_owned_by_another_tenant():
    repo = FakeChunkRepo({BOT: {"mine": chunk("mine")}, OTHER_BOT: {"theirs": chunk("theirs")}})
    # Simulates a corrupted / misrouted index returning someone else's chunk id.
    retriever = StaticRetriever("vector", ["theirs", "mine"])
    result = RetrievalService(retriever, repo).retrieve(BOT, "q", top_n=5)
    assert [c.chunk_id for c in result.chunks] == ["mine"]


def test_service_with_no_hits():
    result = RetrievalService(StaticRetriever("vector", []), FakeChunkRepo({})).retrieve(BOT, "q", 5)
    assert result.chunks == [] and result.top_vector_score == 0.0
