"""Keeping documents and their chunks between runs.

DocumentStore is the base class. MemoryStore keeps everything in a dict
and forgets it when the program ends (good for tests and the demo).
SqliteStore saves to a database file, so documents you add today are still
there tomorrow.

The search index isn't saved. It's rebuilt from the saved chunks when the
program starts, which takes a moment even for hundreds of documents, and
means the index can never get out of step with the database.
"""

from __future__ import annotations

import sqlite3
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterable, Iterator

from .models import Chunk, Document

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    doc_id  TEXT PRIMARY KEY,
    title   TEXT NOT NULL,
    source  TEXT NOT NULL,
    text    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS chunks (
    doc_id  TEXT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    idx     INTEGER NOT NULL,
    text    TEXT NOT NULL,
    start   INTEGER NOT NULL,
    finish  INTEGER NOT NULL,
    PRIMARY KEY (doc_id, idx)
);
"""


class DocumentStore(ABC):
    """Somewhere to keep documents and their chunks."""

    @abstractmethod
    def add(self, document: Document, chunks: Iterable[Chunk]) -> bool:
        """Save a document and its chunks. Returns False if it was already there."""

    @abstractmethod
    def get(self, doc_id: str) -> Document | None:
        """One document, or None."""

    @abstractmethod
    def documents(self) -> list[Document]:
        """Every document, in the order they were added."""

    @abstractmethod
    def chunks(self, doc_id: str | None = None) -> list[Chunk]:
        """Every chunk, or just one document's, in order."""

    @abstractmethod
    def remove(self, doc_id: str) -> bool:
        """Delete a document and its chunks. Returns False if it wasn't there."""

    def __len__(self) -> int:
        return len(self.documents())

    def __iter__(self) -> Iterator[Document]:
        return iter(self.documents())


class MemoryStore(DocumentStore):
    """Keeps everything in memory. Gone when the program ends."""

    def __init__(self) -> None:
        self._documents: dict[str, Document] = {}
        self._chunks: dict[str, list[Chunk]] = {}

    def add(self, document: Document, chunks: Iterable[Chunk]) -> bool:
        if document.doc_id in self._documents:
            return False
        self._documents[document.doc_id] = document
        self._chunks[document.doc_id] = sorted(chunks, key=lambda c: c.index)
        return True

    def get(self, doc_id: str) -> Document | None:
        return self._documents.get(doc_id)

    def documents(self) -> list[Document]:
        return list(self._documents.values())

    def chunks(self, doc_id: str | None = None) -> list[Chunk]:
        if doc_id is not None:
            return list(self._chunks.get(doc_id, []))
        return [c for chunks in self._chunks.values() for c in chunks]

    def remove(self, doc_id: str) -> bool:
        self._chunks.pop(doc_id, None)
        return self._documents.pop(doc_id, None) is not None


class SqliteStore(DocumentStore):
    """Saves documents and chunks in a SQLite database file.

    Pass ":memory:" for a database that only lives in memory.
    """

    def __init__(self, path: str | Path = ":memory:") -> None:
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock, self._conn:
            self._conn.execute("PRAGMA foreign_keys = ON")
            self._conn.executescript(SCHEMA)

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> SqliteStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def add(self, document: Document, chunks: Iterable[Chunk]) -> bool:
        rows = [(c.doc_id, c.index, c.text, c.start, c.end) for c in chunks]
        # The "with self._conn" block is one transaction: all of it is saved, or none.
        with self._lock, self._conn:
            try:
                self._conn.execute("INSERT INTO documents VALUES (?, ?, ?, ?)",
                                   (document.doc_id, document.title, document.source,
                                    document.text))
            except sqlite3.IntegrityError:
                return False
            self._conn.executemany("INSERT INTO chunks VALUES (?, ?, ?, ?, ?)", rows)
        return True

    def get(self, doc_id: str) -> Document | None:
        row = self._query("SELECT doc_id, title, text, source FROM documents WHERE doc_id = ?",
                          (doc_id,))
        return Document(*row[0]) if row else None

    def documents(self) -> list[Document]:
        rows = self._query("SELECT doc_id, title, text, source FROM documents ORDER BY rowid")
        return [Document(*row) for row in rows]

    def chunks(self, doc_id: str | None = None) -> list[Chunk]:
        sql = "SELECT doc_id, idx, text, start, finish FROM chunks"
        if doc_id is None:
            rows = self._query(sql + " ORDER BY doc_id, idx")
        else:
            rows = self._query(sql + " WHERE doc_id = ? ORDER BY idx", (doc_id,))
        return [Chunk(*row) for row in rows]

    def remove(self, doc_id: str) -> bool:
        with self._lock, self._conn:
            # Its chunks go too, because of ON DELETE CASCADE.
            cursor = self._conn.execute("DELETE FROM documents WHERE doc_id = ?", (doc_id,))
        return cursor.rowcount > 0

    def _query(self, sql: str, params: tuple = ()) -> list[tuple]:
        with self._lock:
            return self._conn.execute(sql, params).fetchall()
