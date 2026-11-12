"""The two main things the program works with: documents and chunks.

A document is one whole file, like a tenancy agreement. A chunk is a small
piece of it, a few sentences long. We search chunks rather than whole
documents, so an answer can point to the exact part it came from.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from .exceptions import ValidationError


def make_doc_id(text: str) -> str:
    """A short id worked out from the text, so the same text always gets the same id."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


@dataclass(frozen=True)
class Document:
    """One whole document."""

    doc_id: str
    title: str
    text: str
    source: str = ""

    def __post_init__(self) -> None:
        if not self.doc_id.strip():
            raise ValidationError("A document needs an id.")
        if not self.title.strip():
            raise ValidationError("A document needs a title.")
        if not self.text.strip():
            raise ValidationError(f"{self.title!r} has no text in it.")
        object.__setattr__(self, "title", self.title.strip())

    @classmethod
    def create(cls, title: str, text: str, source: str = "") -> Document:
        """Make a document and give it an id based on its text."""
        return cls(make_doc_id(text), title, text, source)

    @property
    def word_count(self) -> int:
        return len(self.text.split())


@dataclass(frozen=True)
class Chunk:
    """A small piece of a document.

    start and end are character positions in the document's text, so
    document.text[start:end] gives this chunk's text back.
    """

    doc_id: str
    index: int
    text: str
    start: int
    end: int

    def __post_init__(self) -> None:
        if self.index < 0:
            raise ValidationError("A chunk's index can't be negative.")
        if not self.text.strip():
            raise ValidationError("A chunk needs some text.")
        if not 0 <= self.start < self.end:
            raise ValidationError(f"Bad chunk position {self.start}-{self.end}.")

    @property
    def chunk_id(self) -> str:
        """Unique across every document, e.g. 'a1b2c3d4e5f6:3'."""
        return f"{self.doc_id}:{self.index}"

    def short(self, length: int = 80) -> str:
        """The first part of the text on one line, for lists and citations."""
        flat = " ".join(self.text.split())
        return flat if len(flat) <= length else flat[: length - 3].rstrip() + "..."
