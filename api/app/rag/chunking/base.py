"""Chunker strategy interface.

`chunk()` is a template method: it walks sections and delegates the actual splitting of each
section's text to the strategy's `split()`. Strategies that need section-level control
(e.g. heading-aware splitting) override `chunk_section()` instead.
"""

from abc import ABC, abstractmethod
from typing import ClassVar

from app.domain.types import Section, TextChunk


class Chunker(ABC):
    name: ClassVar[str]
    description: ClassVar[str]

    def __init__(self, max_tokens: int = 400, overlap_tokens: int = 60):
        if overlap_tokens >= max_tokens:
            raise ValueError("overlap_tokens must be smaller than max_tokens")
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens

    def chunk(self, sections: list[Section]) -> list[TextChunk]:
        chunks: list[TextChunk] = []
        for section in sections:
            chunks.extend(self.chunk_section(section))
        return chunks

    def chunk_section(self, section: Section) -> list[TextChunk]:
        return [
            TextChunk(content=piece.strip(), heading=section.heading, meta=dict(section.meta))
            for piece in self.split(section.text)
            if piece.strip()
        ]

    @abstractmethod
    def split(self, text: str) -> list[str]:
        """Split raw text into chunk-sized strings."""
