"""Reading files into Document objects.

Each kind of file has its own loader class. The LoaderRegistry looks at the
file's ending (.txt, .md...) and hands it to the right loader, a bit like a
post room putting letters in the right pigeonhole.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from pathlib import Path

from .exceptions import LoaderError
from .models import Document


class DocumentLoader(ABC):
    """Turns one kind of file into a Document."""

    # The file endings this loader can read, e.g. (".txt",).
    extensions: tuple[str, ...] = ()

    def can_load(self, path: Path) -> bool:
        return path.suffix.lower() in self.extensions

    def load(self, path: str | Path) -> Document:
        path = Path(path)
        if not path.is_file():
            raise LoaderError(f"No file at {path}.")
        text = self.read_text(path)
        if not text.strip():
            raise LoaderError(f"{path.name} is empty.")
        return Document.create(self.title_for(path, text), text, str(path))

    @abstractmethod
    def read_text(self, path: Path) -> str:
        """Return the plain text inside the file."""

    def title_for(self, path: Path, text: str) -> str:
        """The file name, tidied up: 'tenancy_agreement.txt' becomes 'Tenancy agreement'."""
        name = re.sub(r"[_\-]+", " ", path.stem).strip()
        return name[:1].upper() + name[1:] if name else path.name


def read_utf8(path: Path) -> str:
    """Read a text file. utf-8-sig also copes with files saved by Notepad."""
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        raise LoaderError(f"{path.name} isn't a UTF-8 text file.") from None


class TextLoader(DocumentLoader):
    """Plain .txt files."""

    extensions = (".txt",)

    def read_text(self, path: Path) -> str:
        return read_utf8(path)


class MarkdownLoader(DocumentLoader):
    """Markdown .md files. Takes the title from the first heading and strips the symbols."""

    extensions = (".md", ".markdown")

    def read_text(self, path: Path) -> str:
        return read_utf8(path)

    def title_for(self, path: Path, text: str) -> str:
        match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
        return match.group(1).strip() if match else super().title_for(path, text)

    def load(self, path: str | Path) -> Document:
        document = super().load(path)
        plain = strip_markdown(document.text)
        return Document.create(document.title, plain, document.source)


def strip_markdown(text: str) -> str:
    """Remove the markdown symbols but keep the words."""
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)  # links and images keep their words
    text = re.sub(r"(\*\*|__|\*|_|`)", "", text)
    text = re.sub(r"^\s*[-+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*>\s?", "", text, flags=re.MULTILINE)
    return text.strip()


class LoaderRegistry:
    """Finds the right loader for a file by its ending."""

    def __init__(self, loaders: list[DocumentLoader] | None = None) -> None:
        self._loaders = list(loaders) if loaders is not None else [TextLoader(), MarkdownLoader()]

    def register(self, loader: DocumentLoader) -> None:
        self._loaders.append(loader)

    @property
    def extensions(self) -> list[str]:
        return sorted({ext for loader in self._loaders for ext in loader.extensions})

    def loader_for(self, path: str | Path) -> DocumentLoader:
        path = Path(path)
        for loader in self._loaders:
            if loader.can_load(path):
                return loader
        raise LoaderError(f"Can't read {path.suffix or 'files with no ending'} files. "
                          f"Try one of: {', '.join(self.extensions)}.")

    def load(self, path: str | Path) -> Document:
        return self.loader_for(path).load(path)
