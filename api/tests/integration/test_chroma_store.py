import pytest

pytestmark = pytest.mark.integration


def test_upsert_query_and_delete(chroma_namespace):
    store, ns = chroma_namespace
    store.upsert(ns, ["a", "b", "c"], [[1, 0], [0.9, 0.1], [0, 1]], ["A", "B", "C"],
                 [{"document_id": "d1"}, {"document_id": "d1"}, {"document_id": "d2"}])

    hits = store.query(ns, [1, 0], k=2)
    assert [h.chunk_id for h in hits] == ["a", "b"]
    assert hits[0].score == pytest.approx(1.0, abs=1e-4)

    store.delete_document(ns, "d1")
    assert [h.chunk_id for h in store.query(ns, [1, 0], k=5)] == ["c"]


def test_query_on_empty_or_missing_namespace_returns_nothing(chroma_namespace):
    store, ns = chroma_namespace
    assert store.query(ns, [1, 0], k=5) == []


def test_namespaces_are_isolated(chroma_namespace):
    store, ns = chroma_namespace
    other = ns + "_other"
    try:
        store.upsert(ns, ["mine"], [[1, 0]], ["x"], [{"document_id": "d"}])
        store.upsert(other, ["theirs"], [[1, 0]], ["y"], [{"document_id": "d"}])
        assert [h.chunk_id for h in store.query(ns, [1, 0], k=5)] == ["mine"]
    finally:
        store.drop_namespace(other)
