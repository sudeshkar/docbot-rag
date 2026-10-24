import json
import math

import httpx
import pytest

from app.rag.embeddings.base import Embedder
from app.rag.embeddings.cached import CachedEmbedder
from app.rag.embeddings.factory import create_embedder
from app.rag.embeddings.hashing import HashEmbedder
from app.rag.embeddings.voyage import VoyageEmbedder


def cosine(a, b):
    return sum(x * y for x, y in zip(a, b))


# --- hashing ---------------------------------------------------------------------

def test_hash_embedder_is_deterministic_and_unit_norm():
    e = HashEmbedder(dim=256)
    a, b = e.embed_documents(["refund policy", "refund policy"])
    assert a == b
    assert math.isclose(math.sqrt(sum(x * x for x in a)), 1.0, rel_tol=1e-9)
    assert len(a) == 256


def test_hash_embedder_similar_texts_score_higher():
    e = HashEmbedder()
    q = e.embed_query("how do refunds work")
    near = e.embed_query("refunds work within 5 days")
    far = e.embed_query("shipping to canada takes a week")
    assert cosine(q, near) > cosine(q, far)


# --- voyage (HTTP mocked) --------------------------------------------------------------

def make_voyage(handler, batch_size=2):
    return VoyageEmbedder(
        api_key="test-key",
        model="voyage-3.5",
        batch_size=batch_size,
        transport=httpx.MockTransport(handler),
    )


def test_voyage_batches_requests_and_restores_order():
    calls = []

    def handler(request: httpx.Request):
        body = json.loads(request.content)
        calls.append(body)
        assert request.headers["authorization"] == "Bearer test-key"
        # return out of order to prove we sort by index
        data = [{"index": i, "embedding": [float(len(t))]} for i, t in enumerate(body["input"])]
        return httpx.Response(200, json={"data": list(reversed(data))})

    out = make_voyage(handler).embed_documents(["a", "bb", "ccc"])
    assert out == [[1.0], [2.0], [3.0]]
    assert [len(c["input"]) for c in calls] == [2, 1]
    assert all(c["input_type"] == "document" for c in calls)


def test_voyage_query_uses_query_input_type():
    seen = {}

    def handler(request):
        seen.update(json.loads(request.content))
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [0.5]}]})

    assert make_voyage(handler).embed_query("hi") == [0.5]
    assert seen["input_type"] == "query"


def test_voyage_raises_on_http_error():
    with pytest.raises(httpx.HTTPStatusError):
        make_voyage(lambda r: httpx.Response(401, json={})).embed_query("hi")


def test_voyage_requires_key():
    with pytest.raises(ValueError):
        VoyageEmbedder(api_key="", model="voyage-3.5")


# --- cached decorator -----------------------------------------------------------

class CountingEmbedder(Embedder):
    def __init__(self):
        self.query_calls = 0
        self.doc_calls = 0

    def embed_documents(self, texts):
        self.doc_calls += 1
        return [[float(len(t))] for t in texts]

    def embed_query(self, text):
        self.query_calls += 1
        return [float(len(text))]


def test_cached_embedder_memoizes_queries_with_lru_eviction():
    inner = CountingEmbedder()
    cached = CachedEmbedder(inner, max_size=2)
    cached.embed_query("a")
    cached.embed_query("a")
    assert inner.query_calls == 1
    cached.embed_query("b")
    cached.embed_query("a")  # refresh "a" -> "b" is now least recently used
    cached.embed_query("c")  # evicts "b"
    assert inner.query_calls == 3
    cached.embed_query("a")
    assert inner.query_calls == 3
    cached.embed_query("b")
    assert inner.query_calls == 4


def test_cached_embedder_normalizes_whitespace_and_case():
    inner = CountingEmbedder()
    cached = CachedEmbedder(inner)
    cached.embed_query("Refund  Policy")
    cached.embed_query(" refund policy ")
    assert inner.query_calls == 1


def test_cached_embedder_returns_copies_so_callers_cannot_poison_cache():
    cached = CachedEmbedder(CountingEmbedder())
    v = cached.embed_query("abc")
    v[0] = 999.0
    assert cached.embed_query("abc") == [3.0]


def test_cached_embedder_passes_documents_through():
    inner = CountingEmbedder()
    CachedEmbedder(inner).embed_documents(["x", "y"])
    assert inner.doc_calls == 1


# --- factory ------------------------------------------------------------------

def test_factory_builds_providers():
    assert isinstance(create_embedder("hash"), CachedEmbedder)
    assert isinstance(create_embedder("voyage", voyage_api_key="k"), CachedEmbedder)
    with pytest.raises(ValueError):
        create_embedder("nope")
