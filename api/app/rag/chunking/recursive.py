from app.rag.chunking.base import Chunker
from app.rag.chunking.registry import register_chunker
from app.rag.chunking.text_utils import approx_tokens, max_words

DEFAULT_SEPARATORS = ["\n\n", "\n", ". ", "? ", "! ", "; ", ", ", " "]


@register_chunker
class RecursiveChunker(Chunker):
    """Split on the coarsest separator that works (paragraph > line > sentence > word),
    recursing into pieces that are still too large, then greedily pack pieces up to the
    token budget with tail overlap between neighbouring chunks."""

    name = "recursive"
    description = "Recursive split on paragraphs, lines, sentences, then words"

    def __init__(self, max_tokens: int = 400, overlap_tokens: int = 60, separators: list[str] | None = None):
        super().__init__(max_tokens, overlap_tokens)
        self.separators = separators or DEFAULT_SEPARATORS

    def split(self, text: str) -> list[str]:
        return self._merge(self._split(text, self.separators))

    def _split(self, text: str, separators: list[str]) -> list[str]:
        if approx_tokens(text) <= self.max_tokens:
            return [text]
        for i, sep in enumerate(separators):
            if sep not in text:
                continue
            parts = text.split(sep)
            # Keep the separator attached so merged chunks read naturally.
            pieces = [p + sep for p in parts[:-1]] + [parts[-1]]
            out: list[str] = []
            for piece in pieces:
                if not piece.strip():
                    continue
                if approx_tokens(piece) > self.max_tokens:
                    out.extend(self._split(piece, separators[i + 1 :]))
                else:
                    out.append(piece)
            return out
        # No separator left: hard split on words.
        words = text.split()
        size = max_words(self.max_tokens)
        return [" ".join(words[i : i + size]) for i in range(0, len(words), size)]

    def _merge(self, pieces: list[str]) -> list[str]:
        chunks: list[str] = []
        current: list[str] = []
        for piece in pieces:
            if current and approx_tokens("".join(current) + piece) > self.max_tokens:
                chunks.append("".join(current).strip())
                current = self._overlap_tail(current)
            current.append(piece)
        if current and "".join(current).strip():
            chunks.append("".join(current).strip())
        return chunks

    def _overlap_tail(self, pieces: list[str]) -> list[str]:
        tail: list[str] = []
        for piece in reversed(pieces):
            if approx_tokens("".join([piece] + tail)) > self.overlap_tokens:
                break
            tail.insert(0, piece)
        return tail
