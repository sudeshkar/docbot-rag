from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar

from app.domain.types import LoadedDocument


class FileLoader(ABC):
    extensions: ClassVar[frozenset[str]]

    @abstractmethod
    def load(self, path: Path, display_name: str) -> LoadedDocument: ...
