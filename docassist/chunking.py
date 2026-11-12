"""Cutting documents into chunks.

Why overlap? Imagine cutting a recipe into cards. If one step is split
across two cards, neither card makes sense alone. Repeating the last
sentence of each chunk at the start of the next one stops an answer
from being cut in half.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from .exceptions import ValidationError
from .models import Chunk, Document
from .text import sentence_spans


class Chunker(ABC):
    """Cuts a document into chunks."""

    @abstractmethod
    def split(self, document: Document) -> list[Chunk]:
        """Return the chunks in order. Index 0 is the first."""


class SentenceChunker(Chunker):
    """Groups whole sentences into chunks of about max_words words.

    A sentence is never cut in half. overlap is how many sentences from the
    end of one chunk are repeated at the start of the next.
    """

    def __init__(self, max_words: int = 120, overlap: int = 1) -> None:
        if max_words < 1:
            raise ValidationError("max_words must be at least 1.")
        if overlap < 0:
            raise ValidationError("overlap can't be negative.")
        self.max_words = max_words
        self.overlap = overlap

    def split(self, document: Document) -> list[Chunk]:
        spans = sentence_spans(document.text)
        counts = [len(document.text[s:e].split()) for s, e in spans]
        groups: list[tuple[int, int]] = []  # (first sentence, last sentence + 1)
        first = 0
        # A document always has at least one sentence, so this loop always ends.
        while True:
            last, words = first, 0
            # Always take at least one sentence, even a very long one.
            while last < len(spans) and (last == first or words + counts[last] <= self.max_words):
                words += counts[last]
                last += 1
            groups.append((first, last))
            if last == len(spans):
                break
            # Step back for the overlap, but always move forward at least one.
            first = max(last - self.overlap, first + 1)
        return [self._chunk(document, i, spans[a][0], spans[b - 1][1])
                for i, (a, b) in enumerate(groups)]

    @staticmethod
    def _chunk(document: Document, index: int, start: int, end: int) -> Chunk:
        return Chunk(document.doc_id, index, document.text[start:end], start, end)
