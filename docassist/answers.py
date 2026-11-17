"""Turning search results into an answer, with sources.

The ExtractiveAnswerer doesn't make anything up. It picks the sentences
from the found chunks that best match the question and quotes them, with a
number like [1] that says which document each one came from. Think of a
student answering with a highlighter and page numbers, not their own words.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Mapping, Sequence

from .exceptions import ValidationError
from .llm import Message
from .search import SearchHit
from .text import sentences, tokens

NOT_FOUND = "I couldn't find anything about that in your documents."


@dataclass(frozen=True)
class Source:
    """Where part of an answer came from."""

    number: int
    doc_id: str
    title: str
    chunk_id: str
    snippet: str

    def label(self) -> str:
        return f"[{self.number}] {self.title}: \"{self.snippet}\""


@dataclass(frozen=True)
class Answer:
    """An answer to one question."""

    question: str
    text: str
    sources: tuple[Source, ...] = ()

    @property
    def found(self) -> bool:
        return bool(self.sources)

    @classmethod
    def not_found(cls, question: str) -> Answer:
        return cls(question, NOT_FOUND)

    def render(self) -> str:
        """The answer followed by its sources, ready to print."""
        lines = [self.text]
        if self.sources:
            lines += ["", "Sources:"] + [f"  {s.label()}" for s in self.sources]
        return "\n".join(lines)


def shorten(text: str, length: int = 80) -> str:
    return text if len(text) <= length else text[: length - 3].rstrip() + "..."


def looks_like_heading(sentence: str) -> bool:
    """A few words with no full stop, like "Deposit" or "Ending the tenancy"."""
    return len(sentence.split()) <= 5 and not sentence.endswith((".", "!", "?"))


class SourceList:
    """Gives each chunk a number the first time it's used, so [1] always means the same place."""

    def __init__(self, titles: Mapping[str, str]) -> None:
        self._titles = titles
        self._numbers: dict[str, Source] = {}

    def number_for(self, hit: SearchHit, snippet: str = "") -> int:
        """The chunk's number. snippet is the bit to show for it (the chunk's start if not given)."""
        chunk = hit.chunk
        if chunk.chunk_id not in self._numbers:
            self._numbers[chunk.chunk_id] = Source(
                len(self._numbers) + 1, chunk.doc_id,
                self._titles.get(chunk.doc_id, "Unknown document"), chunk.chunk_id,
                shorten(snippet) if snippet else chunk.short())
        return self._numbers[chunk.chunk_id].number

    def sources(self) -> tuple[Source, ...]:
        return tuple(self._numbers.values())


class AnswerEngine(ABC):
    """Answers a question using the chunks a search found."""

    @abstractmethod
    def answer(self, question: str, hits: Sequence[SearchHit], titles: Mapping[str, str],
               history: Sequence[Message] = ()) -> Answer:
        """titles maps each doc_id to its document's title, for the sources.

        history is the conversation so far, oldest first. Engines that can't
        use it just ignore it.
        """


class ExtractiveAnswerer(AnswerEngine):
    """Answers by quoting the best matching sentences. Works offline, never makes things up."""

    def __init__(self, max_sentences: int = 3) -> None:
        if max_sentences < 1:
            raise ValidationError("max_sentences must be at least 1.")
        self.max_sentences = max_sentences

    def answer(self, question: str, hits: Sequence[SearchHit], titles: Mapping[str, str],
               history: Sequence[Message] = ()) -> Answer:
        wanted = set(tokens(question))
        candidates = []
        seen: set[str] = set()
        for rank, hit in enumerate(hits):
            for position, sentence in enumerate(sentences(hit.chunk.text)):
                # Overlapping chunks repeat sentences, so only keep the first copy.
                # Headings aren't answers, so skip those too.
                if sentence in seen or looks_like_heading(sentence):
                    continue
                seen.add(sentence)
                shared = len(wanted & set(tokens(sentence)))
                if shared:
                    # More shared words first, then the better search hit, then earlier in the chunk.
                    candidates.append(((-shared, rank, position), sentence, hit))
        if not candidates:
            return Answer.not_found(question)
        candidates.sort(key=lambda c: c[0])
        sources = SourceList(titles)
        parts = [f"{sentence} [{sources.number_for(hit, sentence)}]"
                 for _, sentence, hit in candidates[: self.max_sentences]]
        return Answer(question, " ".join(parts), sources.sources())
