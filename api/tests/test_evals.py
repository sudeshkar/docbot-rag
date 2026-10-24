import pytest

from evals.indexes import BM25Index, VectorIndex
from evals.metrics import mean_reciprocal_rank, recall_at_k


def test_recall_at_k():
    # each inner list = relevance of ranked results for one query
    runs = [[False, True, False], [False, False, False], [True]]
    assert recall_at_k(runs, 1) == pytest.approx(1 / 3)
    assert recall_at_k(runs, 2) == pytest.approx(2 / 3)


def test_mrr():
    assert mean_reciprocal_rank([[False, True], [True], [False, False]]) == pytest.approx((0.5 + 1 + 0) / 3)


def test_bm25_ranks_rare_matching_terms_higher():
    index = BM25Index()
    index.add("a", "refunds are issued within 5 business days")
    index.add("b", "the plan costs 8 dollars per month and the plan includes storage")
    index.add("c", "error E-507 means your storage is full")
    assert [cid for cid, _ in index.search("how long do refunds take", 3)] == ["a"]
    assert index.search("storage", 3)[0][0] in {"b", "c"}
    assert index.search("e-507 error", 1)[0][0] == "c"
    assert index.search("zzz", 3) == []


def test_vector_index_returns_top_k_by_cosine():
    index = VectorIndex()
    index.add("x", [1.0, 0.0])
    index.add("y", [0.7, 0.7])
    index.add("z", [0.0, 1.0])
    assert [cid for cid, _ in index.search([1.0, 0.1], 2)] == ["x", "y"]
