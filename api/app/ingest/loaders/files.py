from pathlib import Path

import pymupdf

from app.domain.types import LoadedDocument, Section
from app.ingest.loaders.base import FileLoader


class TextLoader(FileLoader):
    extensions = frozenset({".md", ".markdown", ".txt"})

    def load(self, path: Path, display_name: str) -> LoadedDocument:
        text = path.read_text(encoding="utf-8", errors="replace")
        return LoadedDocument(title=display_name, sections=[Section(text=text)])


class PdfLoader(FileLoader):
    """One section per page so citations can point at a page number."""

    extensions = frozenset({".pdf"})

    def load(self, path: Path, display_name: str) -> LoadedDocument:
        sections = []
        with pymupdf.open(path) as pdf:
            for page_no, page in enumerate(pdf, start=1):
                text = page.get_text("text").strip()
                if text:
                    sections.append(Section(text=text, meta={"page": page_no}))
        return LoadedDocument(title=display_name, sections=sections)
