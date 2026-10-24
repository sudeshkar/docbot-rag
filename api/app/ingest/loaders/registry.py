from pathlib import Path

from app.domain.types import LoadedDocument
from app.ingest.loaders.base import FileLoader
from app.ingest.loaders.files import PdfLoader, TextLoader

# Extension -> loader: O(1) dispatch, and adding a format is one new class + one line here.
_LOADERS: dict[str, FileLoader] = {}
for _loader in (TextLoader(), PdfLoader()):
    for _ext in _loader.extensions:
        _LOADERS[_ext] = _loader


def load_file(path: Path, display_name: str) -> LoadedDocument:
    loader = _LOADERS.get(path.suffix.lower())
    if loader is None:
        raise ValueError(f"No loader for '{path.suffix}' files")
    return loader.load(path, display_name)
