import math

from app.domain.types import Section, TextChunk
from app.rag.chunking.base import Chunker
from app.rag.chunking.markdown import heading_subsections
from app.rag.chunking.recursive import RecursiveChunker
from app.rag.chunking.registry import register_chunker
from app.rag.chunking.text_utils import approx_tokens, split_sentences
from app.rag.embeddings.base import Embedder


def _cosine_distance(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return 1.0 - dot / (na * nb)


def _percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, round(pct / 100 * (len(ordered) - 1))))
    return ordered[idx]


@register_chunker
class SemanticChunker(Chunker):
    """Embed each sentence and cut where the meaning shifts: wherever the cosine distance between
    adjacent sentences is in the top (100 - breakpoint_percentile)% for that section. Groups that
    exceed the budget fall back to recursive splitting; tiny groups merge into their neighbour."""

    name = "semantic"
    description = "Embedding-based: breaks where adjacent sentences diverge in meaning"
    requires_embedder = True

    def __init__(
        self,
        embedder: Embedder,
        max_tokens: int = 400,
        overlap_tokens: int = 60,
        breakpoint_percentile: float = 90,
        min_tokens: int = 40,
    ):
        super().__init__(max_tokens, overlap_tokens)
        self.embedder = embedder
        self.breakpoint_percentile = breakpoint_percentile
        self.min_tokens = min_tokens
        self._fallback = RecursiveChunker(max_tokens, overlap_tokens)

    def chunk_section(self, section: Section) -> list[TextChunk]:
        chunks: list[TextChunk] = []
        for sub in heading_subsections(section):
            chunks.extend(super().chunk_section(sub))
        return chunks

    def split(self, text: str) -> list[str]:
        sentences = split_sentences(text)
        if len(sentences) < 3:
            return self._fallback.split(text)

        vectors = self.embedder.embed_documents(sentences)
        distances = [_cosine_distance(a, b) for a, b in zip(vectors, vectors[1:])]
        threshold = _percentile(distances, self.breakpoint_percentile)

        groups: list[list[str]] = [[sentences[0]]]
        for sentence, dist in zip(sentences[1:], distances):
            if dist >= threshold and approx_tokens(" ".join(groups[-1])) >= self.min_tokens:
                groups.append([sentence])
            else:
                groups[-1].append(sentence)

        out: list[str] = []
        for group in groups:
            joined = " ".join(group)
            out.extend(self._fallback.split(joined) if approx_tokens(joined) > self.max_tokens else [joined])
        return out
