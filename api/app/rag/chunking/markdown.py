from app.domain.types import Section, TextChunk
from app.rag.chunking.recursive import RecursiveChunker
from app.rag.chunking.registry import register_chunker
from app.rag.chunking.text_utils import split_by_headings


def heading_subsections(section: Section) -> list[Section]:
    """Split a section on its markdown headings, nesting under any heading the loader already set."""
    out = []
    for heading, body in split_by_headings(section.text):
        full = " > ".join(h for h in (section.heading, heading) if h) or None
        out.append(Section(text=body, heading=full, meta=dict(section.meta)))
    return out


@register_chunker
class MarkdownChunker(RecursiveChunker):
    """Structure-aware: never lets a chunk straddle two headings, and records the heading path
    ("Billing > Refunds") on each chunk so it can be shown in citations and prepended for embedding."""

    name = "markdown"
    description = "Heading-aware: splits on markdown structure, then recursively within sections"

    def chunk_section(self, section: Section) -> list[TextChunk]:
        chunks: list[TextChunk] = []
        for sub in heading_subsections(section):
            chunks.extend(super().chunk_section(sub))
        return chunks
