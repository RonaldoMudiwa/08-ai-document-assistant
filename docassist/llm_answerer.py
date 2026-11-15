"""Answers written by a real AI model, still based only on your documents.

The model is handed the chunks the search found, each with a number, and
told to answer only from them and to put the number after each fact. This
is called retrieval augmented generation (RAG): look things up first, then
write. It's like an open book exam. The model can word things nicely, but
the facts have to come from the book.
"""

from __future__ import annotations

import re
from typing import Mapping, Sequence

from .answers import NOT_FOUND, Answer, AnswerEngine, SourceList
from .exceptions import ValidationError
from .llm import LLMProvider, Message
from .search import SearchHit

SYSTEM_PROMPT = f"""You answer questions about the user's own documents.

Rules:
- Use ONLY the numbered extracts you are given. Never use outside knowledge.
- After every fact, put the number of the extract it came from, like [2].
- If the extracts don't answer the question, reply with exactly: {NOT_FOUND}
- Keep answers short and in plain English."""

_CITATION = re.compile(r"\[(\d+)\]")


def build_prompt(question: str, extracts: Sequence[tuple[int, str, str]]) -> str:
    """The message sent to the model: the numbered extracts, then the question.

    extracts holds (number, document title, chunk text).
    """
    parts = [f"[{number}] From \"{title}\":\n{text}" for number, title, text in extracts]
    return "Extracts:\n\n" + "\n\n".join(parts) + f"\n\nQuestion: {question}"


class LLMAnswerer(AnswerEngine):
    """Asks an LLMProvider to write the answer from the found chunks."""

    def __init__(self, provider: LLMProvider, max_extracts: int = 5) -> None:
        if max_extracts < 1:
            raise ValidationError("max_extracts must be at least 1.")
        self.provider = provider
        self.max_extracts = max_extracts

    def answer(self, question: str, hits: Sequence[SearchHit],
               titles: Mapping[str, str]) -> Answer:
        hits = list(hits)[: self.max_extracts]
        # Nothing found means nothing to go on, so don't pay for a call.
        if not hits:
            return Answer.not_found(question)
        numbering = SourceList(titles)
        extracts = []
        for hit in hits:
            number = numbering.number_for(hit)
            extracts.append((number, titles.get(hit.chunk.doc_id, "Unknown document"),
                             hit.chunk.text))
        reply = self.provider.complete(SYSTEM_PROMPT,
                                       [Message("user", build_prompt(question, extracts))])
        if NOT_FOUND.lower() in reply.lower():
            return Answer.not_found(question)
        # Only list the sources the model actually used, and ignore made up numbers.
        cited = {int(n) for n in _CITATION.findall(reply)}
        sources = tuple(s for s in numbering.sources() if s.number in cited)
        return Answer(question, reply, sources)
