"""Reading PDF files, using the pypdf library.

pypdf is only imported when a PDF is actually read, so the rest of the
program still works if it isn't installed.
"""

from __future__ import annotations

from pathlib import Path

from .exceptions import LoaderError
from .loaders import DocumentLoader
from .models import Document


class PdfLoader(DocumentLoader):
    """Pulls the text out of every page of a PDF.

    Scanned PDFs are just pictures of pages, so they have no text to pull
    out. Those give a clear error instead of an empty document.
    """

    extensions = (".pdf",)

    def load(self, path: str | Path) -> Document:
        path = Path(path)
        if not path.is_file():
            raise LoaderError(f"No file at {path}.")
        text, title = self._read(path)
        # Use the title saved inside the PDF if it has one.
        return Document.create(title or self.title_for(path, text), text, str(path))

    def read_text(self, path: Path) -> str:
        return self._read(path)[0]

    @staticmethod
    def _read(path: Path) -> tuple[str, str]:
        """The text of every page, and the title saved in the PDF ("" if none)."""
        try:
            from pypdf import PdfReader
            from pypdf.errors import PdfReadError
        except ImportError:  # pragma: no cover - only happens without pypdf installed
            raise LoaderError("Reading PDFs needs pypdf: pip install pypdf") from None
        try:
            reader = PdfReader(str(path))
            pages = [page.extract_text() or "" for page in reader.pages]
            title = (reader.metadata.title if reader.metadata else None) or ""
        except (PdfReadError, ValueError, KeyError) as error:
            raise LoaderError(f"{path.name} couldn't be read as a PDF: {error}") from None
        text = "\n\n".join(page.strip() for page in pages if page.strip())
        if not text:
            raise LoaderError(f"{path.name} has no text to read. It may be a scanned picture.")
        return text, title.strip()
