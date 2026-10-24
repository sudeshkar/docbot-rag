import pytest

from app.domain.types import Section
from app.rag.chunking.factory import available_strategies, create_chunker
from app.rag.chunking.fixed import FixedSizeChunker
from app.rag.chunking.markdown import MarkdownChunker
from app.rag.chunking.recursive import RecursiveChunker
from app.rag.chunking.semantic import SemanticChunker
from app.rag.chunking.text_utils import approx_tokens, split_by_headings, split_sentences


def words(n: int, prefix: str = "w") -> str:
    return " ".join(f"{prefix}{i}" for i in range(n))


class FakeEmbedder:
    """Sentences mentioning 'cat' point one way, everything else another, so the topic shift is obvious."""

    def embed_documents(self, texts):
        return [[1.0, 0.0] if "cat" in t.lower() else [0.0, 1.0] for t in texts]

    def embed_query(self, text):
        return self.embed_documents([text])[0]


# --- text utils -------------------------------------------------------------

def test_split_by_headings_tracks_nested_path():
    md = "# Billing\nintro\n## Refunds\nrefund text\n## Invoices\ninvoice text\n# Shipping\nship text"
    assert split_by_headings(md) == [
        ("Billing", "intro"),
        ("Billing > Refunds", "refund text"),
        ("Billing > Invoices", "invoice text"),
        ("Shipping", "ship text"),
    ]


def test_split_by_headings_keeps_text_before_first_heading():
    assert split_by_headings("preamble\n# A\nbody") == [(None, "preamble"), ("A", "body")]


def test_split_sentences():
    assert split_sentences("One here. Two there! Three? ok") == ["One here.", "Two there!", "Three? ok"]


# --- fixed ------------------------------------------------------------------

def test_fixed_chunks_respect_budget_and_overlap():
    chunker = FixedSizeChunker(max_tokens=26, overlap_tokens=6)  # 20 words, 4 overlap
    chunks = chunker.split(words(50))
    assert all(len(c.split()) <= 20 for c in chunks)
    first, second = chunks[0].split(), chunks[1].split()
    assert first[-4:] == second[:4]
    # every word survives
    assert {w for c in chunks for w in c.split()} == set(words(50).split())


def test_overlap_must_be_smaller_than_budget():
    with pytest.raises(ValueError):
        FixedSizeChunker(max_tokens=10, overlap_tokens=10)


# --- recursive ----------------------------------------------------------------

def test_recursive_keeps_small_text_whole():
    assert RecursiveChunker(max_tokens=100, overlap_tokens=10).split("short text") == ["short text"]


def test_recursive_prefers_paragraph_boundaries():
    para_a, para_b = words(30, "a"), words(30, "b")
    chunks = RecursiveChunker(max_tokens=50, overlap_tokens=5).split(f"{para_a}\n\n{para_b}")
    assert chunks == [para_a, para_b]


def test_recursive_never_exceeds_budget_on_unbroken_text():
    chunker = RecursiveChunker(max_tokens=40, overlap_tokens=8)
    chunks = chunker.split(words(500))
    assert len(chunks) > 1
    assert all(approx_tokens(c) <= 40 + 2 for c in chunks)


def test_recursive_adds_overlap_between_chunks():
    sentences = " ".join(f"Sentence number {i} is here." for i in range(40))
    chunks = RecursiveChunker(max_tokens=40, overlap_tokens=10).split(sentences)
    assert len(chunks) > 2
    last_sentence_of_first = chunks[0].rsplit(".", 2)[-2].strip()
    assert last_sentence_of_first in chunks[1]


# --- markdown -----------------------------------------------------------------

def test_markdown_chunks_never_straddle_headings_and_carry_heading_path():
    md = "# Billing\n## Refunds\nRefunds take 5 days.\n## Invoices\nInvoices are monthly."
    chunks = MarkdownChunker(max_tokens=200, overlap_tokens=20).chunk([Section(md)])
    assert [(c.heading, c.content) for c in chunks] == [
        ("Billing > Refunds", "Refunds take 5 days."),
        ("Billing > Invoices", "Invoices are monthly."),
    ]


def test_markdown_preserves_loader_meta_and_parent_heading():
    chunks = MarkdownChunker().chunk([Section("## Setup\nRun it.", heading="Guide", meta={"page": 3})])
    assert chunks[0].heading == "Guide > Setup"
    assert chunks[0].meta == {"page": 3}


# --- semantic -----------------------------------------------------------------

def test_semantic_breaks_on_topic_shift():
    text = (
        "The cat sleeps all day. A cat likes warm places. Every cat purrs. "
        "Taxes are due in April. File your return online. Late filing costs money."
    )
    chunker = SemanticChunker(FakeEmbedder(), max_tokens=200, overlap_tokens=10, min_tokens=1)
    chunks = chunker.split(text)
    assert len(chunks) == 2
    assert "cat" in chunks[0].lower() and "cat" not in chunks[1].lower()


def test_semantic_falls_back_for_tiny_text():
    chunker = SemanticChunker(FakeEmbedder(), max_tokens=200, overlap_tokens=10)
    assert chunker.split("Just one sentence.") == ["Just one sentence."]


# --- factory ------------------------------------------------------------------

def test_factory_lists_and_builds_every_strategy():
    names = {s["name"] for s in available_strategies()}
    assert names == {"fixed", "recursive", "markdown", "semantic"}
    for name in names:
        chunker = create_chunker(name, 200, 20, embedder=FakeEmbedder())
        assert chunker.name == name


def test_factory_rejects_unknown_and_missing_embedder():
    with pytest.raises(ValueError):
        create_chunker("nope", 200, 20)
    with pytest.raises(ValueError):
        create_chunker("semantic", 200, 20, embedder=None)
