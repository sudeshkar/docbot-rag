from uuid import uuid4

import pymupdf
import pytest

from app.domain.types import Section
from app.ingest.loaders.registry import load_file
from app.ingest.pipeline import DocumentRef, IngestionPipeline
from app.ingest.validation import UploadRejected, validate_upload
from app.rag.chunking.markdown import MarkdownChunker
from app.rag.vectorstores.base import namespace_for


class FakeEmbedder:
    def __init__(self):
        self.seen = []

    def embed_documents(self, texts):
        self.seen.extend(texts)
        return [[float(i)] for i, _ in enumerate(texts)]

    def embed_query(self, text):
        return [0.0]


class FakeStore:
    def __init__(self):
        self.upserts = []
        self.deleted = []

    def upsert(self, namespace, ids, embeddings, documents, metadatas):
        self.upserts.append((namespace, ids, embeddings, documents, metadatas))

    def delete_document(self, namespace, document_id):
        self.deleted.append((namespace, document_id))


class FakeChunkRepo:
    def __init__(self):
        self.replaced = None

    def replace_for_document(self, bot_id, document_id, chunks):
        self.replaced = (bot_id, document_id, chunks)
        return [f"id{i}" for i in range(len(chunks))]


def make_pipeline():
    embedder, store, repo = FakeEmbedder(), FakeStore(), FakeChunkRepo()
    pipeline = IngestionPipeline(lambda name: MarkdownChunker(200, 20), embedder, store, repo)
    return pipeline, embedder, store, repo


DOC = DocumentRef(id=uuid4(), bot_id=uuid4(), title="Help Center")


# --- pipeline -----------------------------------------------------------------------

def test_pipeline_chunks_embeds_with_context_and_upserts_to_bot_namespace():
    pipeline, embedder, store, repo = make_pipeline()
    md = "# Billing\n## Refunds\nRefunds take 5 days.\n## Invoices\nMonthly invoices."
    count = pipeline.index(DOC, [Section(md)], strategy="markdown")

    assert count == 2
    assert store.deleted == [(namespace_for(DOC.bot_id), str(DOC.id))]
    ns, ids, embeddings, documents, metadatas = store.upserts[0]
    assert ns == namespace_for(DOC.bot_id)
    assert ids == ["id0", "id1"]
    assert documents == ["Refunds take 5 days.", "Monthly invoices."]
    assert metadatas == [{"document_id": str(DOC.id)}] * 2
    # contextual chunk header: title + heading path are embedded with the text
    assert embedder.seen[0] == "Help Center\nBilling > Refunds\n\nRefunds take 5 days."


def test_pipeline_drops_duplicate_chunks():
    pipeline, _, _, repo = make_pipeline()
    footer = "Contact us at help@example.com"
    count = pipeline.index(DOC, [Section(footer), Section("Unique."), Section("contact us at  HELP@example.com")],
                           strategy="markdown")
    assert count == 2
    assert [c.content for c in repo.replaced[2]] == [footer, "Unique."]


def test_pipeline_with_no_text_clears_old_vectors_and_returns_zero():
    pipeline, _, store, _ = make_pipeline()
    assert pipeline.index(DOC, [Section("   ")], strategy="markdown") == 0
    assert store.deleted and not store.upserts


# --- loaders --------------------------------------------------------------------------

def test_load_markdown_file(tmp_path):
    p = tmp_path / "guide.md"
    p.write_text("# Title\nbody", encoding="utf-8")
    doc = load_file(p, display_name="guide.md")
    assert doc.title == "guide.md"
    assert doc.sections[0].text == "# Title\nbody"


def test_load_pdf_keeps_page_numbers(tmp_path):
    p = tmp_path / "manual.pdf"
    pdf = pymupdf.open()
    for text in ("First page text", "Second page text"):
        pdf.new_page().insert_text((72, 72), text)
    pdf.save(p)
    pdf.close()
    doc = load_file(p, display_name="manual.pdf")
    assert [(s.meta["page"], s.text) for s in doc.sections] == [(1, "First page text"), (2, "Second page text")]


def test_load_unsupported_extension(tmp_path):
    p = tmp_path / "x.exe"
    p.write_bytes(b"MZ")
    with pytest.raises(ValueError):
        load_file(p, display_name="x.exe")


# --- upload validation ------------------------------------------------------------------

def test_validate_upload_accepts_allowed_types():
    assert validate_upload("Guide.MD", b"# hi", size=10) == ".md"
    assert validate_upload("a.pdf", b"%PDF-1.7 ...", size=10) == ".pdf"


@pytest.mark.parametrize(
    "name,head,size",
    [
        ("evil.exe", b"MZ", 10),              # extension not allowed
        ("fake.pdf", b"<html>", 10),          # pdf extension, wrong magic bytes
        ("big.txt", b"text", 30 * 1024 * 1024),  # too large
        ("bin.txt", b"\x00\x01\x02", 10),     # binary disguised as text
        ("", b"x", 1),                        # no name
    ],
)
def test_validate_upload_rejects(name, head, size):
    with pytest.raises(UploadRejected):
        validate_upload(name, head, size)
