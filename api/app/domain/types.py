"""Plain domain objects passed between layers. No ORM or framework imports here."""

from dataclasses import dataclass, field


@dataclass
class Section:
    """A span of source text as a loader produced it (a whole file, a PDF page, a web page)."""

    text: str
    heading: str | None = None
    meta: dict = field(default_factory=dict)


@dataclass
class LoadedDocument:
    title: str
    sections: list[Section]
    source_url: str | None = None


@dataclass
class TextChunk:
    content: str
    heading: str | None = None
    meta: dict = field(default_factory=dict)


@dataclass
class ScoredId:
    """A retrieval hit. `signals` keeps each retriever's raw score so fusion doesn't lose them."""

    chunk_id: str
    score: float
    signals: dict[str, float] = field(default_factory=dict)


@dataclass
class RetrievedChunk:
    chunk_id: str
    document_id: str
    document_title: str
    source_url: str | None
    heading: str | None
    content: str
    meta: dict
    score: float
    signals: dict[str, float] = field(default_factory=dict)


@dataclass
class RetrievalResult:
    chunks: list[RetrievedChunk] = field(default_factory=list)
    # Best raw vector similarity across candidates: our "is this question covered by the docs" signal.
    top_vector_score: float = 0.0
