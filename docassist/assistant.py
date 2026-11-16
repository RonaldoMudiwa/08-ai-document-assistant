"""The DocumentAssistant: one object that ties everything together.

It's the front desk. You hand it files and questions, and behind the desk
it uses the loaders, the chunker, the store, the search index and an
answer engine. Each of those can be swapped for another one that does the
same job, which is how the tests run without files or the internet.
"""

from __future__ import annotations

from pathlib import Path

from .answers import Answer, AnswerEngine, ExtractiveAnswerer
from .chunking import Chunker, SentenceChunker
from .exceptions import NotFoundError, ValidationError
from .history import Conversation
from .loaders import LoaderRegistry
from .models import Document
from .pdf import PdfLoader
from .search import BM25Index, SearchIndex
from .storage import DocumentStore, MemoryStore

# An id prefix shorter than this is too likely to match by accident.
MIN_PREFIX = 4


def default_loaders() -> LoaderRegistry:
    """Text, markdown and PDF."""
    registry = LoaderRegistry()
    registry.register(PdfLoader())
    return registry


class DocumentAssistant:
    """Add documents, then ask questions about them."""

    def __init__(self, store: DocumentStore | None = None, *,
                 engine: AnswerEngine | None = None,
                 index: SearchIndex | None = None,
                 chunker: Chunker | None = None,
                 loaders: LoaderRegistry | None = None,
                 search_limit: int = 5) -> None:
        if search_limit < 1:
            raise ValidationError("search_limit must be at least 1.")
        self.store = store if store is not None else MemoryStore()
        self.engine = engine or ExtractiveAnswerer()
        self.index = index if index is not None else BM25Index()
        self.chunker = chunker or SentenceChunker()
        self.loaders = loaders or default_loaders()
        self.search_limit = search_limit
        # Rebuild the search index from whatever the store already has.
        self.index.add(self.store.chunks())

    def add_file(self, path: str | Path) -> tuple[Document, bool]:
        """Read a file and add it. The bool is False if it was already added."""
        return self.add(self.loaders.load(path))

    def add_text(self, title: str, text: str, source: str = "") -> tuple[Document, bool]:
        return self.add(Document.create(title, text, source))

    def add(self, document: Document) -> tuple[Document, bool]:
        existing = self.store.get(document.doc_id)
        if existing is not None:
            return existing, False
        chunks = self.chunker.split(document)
        self.store.add(document, chunks)
        self.index.add(chunks)
        return document, True

    def documents(self) -> list[Document]:
        return self.store.documents()

    def chunk_count(self, doc_id: str) -> int:
        return len(self.store.chunks(doc_id))

    def find(self, ref: str) -> Document:
        """Find one document by its full title or the start of its id."""
        ref = ref.strip()
        docs = self.store.documents()
        by_title = [d for d in docs if d.title.lower() == ref.lower()]
        by_id = [d for d in docs if len(ref) >= MIN_PREFIX and d.doc_id.startswith(ref.lower())]
        matches = by_title or by_id
        if not matches:
            raise NotFoundError(f"No document called {ref!r}.")
        if len(matches) > 1:
            raise NotFoundError(f"{ref!r} matches {len(matches)} documents. Use more of the id.")
        return matches[0]

    def remove(self, ref: str) -> Document:
        document = self.find(ref)
        self.store.remove(document.doc_id)
        self.index.remove_document(document.doc_id)
        return document

    def ask(self, question: str, conversation: Conversation | None = None) -> Answer:
        """Answer one question. Pass a Conversation to make follow ups work."""
        if not question.strip():
            raise ValidationError("Please ask a question.")
        query = conversation.search_query(question) if conversation else question
        hits = self.index.search(query, self.search_limit)
        titles = {d.doc_id: d.title for d in self.store.documents()}
        history = conversation.messages() if conversation else []
        answer = self.engine.answer(question, hits, titles, history)
        if conversation is not None:
            conversation.add(answer)
        return answer
