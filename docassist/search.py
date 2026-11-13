"""Finding the chunks that best match a question.

BM25 is the scoring method most search engines started with. For each
word in the question it asks two things:

1. Is the word in this chunk, and how often? More is better, but the
   fifth time counts for much less than the first.
2. Is the word rare across all chunks? "deposit" in a tenancy agreement
   tells you a lot. "tenant" is everywhere, so it tells you little.

Long chunks are scored down a little, so they don't win just by having
more words.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from collections import Counter
from dataclasses import dataclass
from typing import Iterable

from .exceptions import ValidationError
from .models import Chunk
from .text import tokens


@dataclass(frozen=True)
class SearchHit:
    """One chunk that matched, and how well. Higher scores are better."""

    chunk: Chunk
    score: float
    matched: tuple[str, ...] = ()


class SearchIndex(ABC):
    """Somewhere to put chunks so they can be searched."""

    @abstractmethod
    def add(self, chunks: Iterable[Chunk]) -> None:
        """Add chunks. A chunk that's already in is replaced."""

    @abstractmethod
    def remove_document(self, doc_id: str) -> int:
        """Take out every chunk from one document. Returns how many went."""

    @abstractmethod
    def search(self, query: str, limit: int = 5) -> list[SearchHit]:
        """Best matches first. Chunks that share no words with the query are left out."""

    @abstractmethod
    def __len__(self) -> int:
        """How many chunks are in the index."""


class BM25Index(SearchIndex):
    """A BM25 search index kept in memory.

    k1 controls how quickly repeating a word stops helping.
    b controls how much long chunks are scored down (0 = not at all, 1 = fully).
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        if k1 < 0:
            raise ValidationError("k1 can't be negative.")
        if not 0 <= b <= 1:
            raise ValidationError("b must be between 0 and 1.")
        self.k1 = k1
        self.b = b
        self._chunks: dict[str, Chunk] = {}
        self._counts: dict[str, Counter[str]] = {}
        self._lengths: dict[str, int] = {}
        # How many chunks each word appears in.
        self._doc_freq: Counter[str] = Counter()

    def __len__(self) -> int:
        return len(self._chunks)

    def __contains__(self, chunk_id: object) -> bool:
        return chunk_id in self._chunks

    def add(self, chunks: Iterable[Chunk]) -> None:
        for chunk in chunks:
            if chunk.chunk_id in self._chunks:
                self._forget(chunk.chunk_id)
            counts = Counter(tokens(chunk.text))
            self._chunks[chunk.chunk_id] = chunk
            self._counts[chunk.chunk_id] = counts
            self._lengths[chunk.chunk_id] = sum(counts.values())
            self._doc_freq.update(counts.keys())

    def remove_document(self, doc_id: str) -> int:
        ids = [cid for cid, chunk in self._chunks.items() if chunk.doc_id == doc_id]
        for chunk_id in ids:
            self._forget(chunk_id)
        return len(ids)

    def _forget(self, chunk_id: str) -> None:
        del self._chunks[chunk_id]
        del self._lengths[chunk_id]
        self._doc_freq.subtract(self._counts.pop(chunk_id).keys())
        self._doc_freq = +self._doc_freq  # drops words that are now in no chunk

    def idf(self, word: str) -> float:
        """How rare a word is. Rare words score higher. Never below zero."""
        total = len(self._chunks)
        having = self._doc_freq.get(word, 0)
        return math.log(1 + (total - having + 0.5) / (having + 0.5))

    def search(self, query: str, limit: int = 5) -> list[SearchHit]:
        if limit < 1:
            raise ValidationError("limit must be at least 1.")
        words = list(dict.fromkeys(tokens(query)))  # no repeats, order kept
        if not words or not self._chunks:
            return []
        average = sum(self._lengths.values()) / len(self._chunks)
        hits = []
        for chunk_id, counts in self._counts.items():
            matched = tuple(w for w in words if w in counts)
            if not matched:
                continue
            scale = 1 - self.b + self.b * self._lengths[chunk_id] / average
            score = sum(self.idf(w) * counts[w] * (self.k1 + 1) / (counts[w] + self.k1 * scale)
                        for w in matched)
            hits.append(SearchHit(self._chunks[chunk_id], score, matched))
        # Ties go to the earlier chunk, so results never jump around.
        hits.sort(key=lambda h: (-h.score, h.chunk.doc_id, h.chunk.index))
        return hits[:limit]
