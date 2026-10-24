from app.rag.chunking.base import Chunker
from app.rag.chunking.registry import register_chunker
from app.rag.chunking.text_utils import max_words


@register_chunker
class FixedSizeChunker(Chunker):
    """Sliding window of N tokens with overlap. Ignores structure: the baseline other strategies beat."""

    name = "fixed"
    description = "Fixed-size token windows with overlap (baseline)"

    def split(self, text: str) -> list[str]:
        words = text.split()
        size = max_words(self.max_tokens)
        step = size - max_words(self.overlap_tokens)
        chunks = []
        for start in range(0, len(words), step):
            chunks.append(" ".join(words[start : start + size]))
            if start + size >= len(words):
                break
        return chunks
