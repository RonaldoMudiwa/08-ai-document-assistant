"""AI Document Assistant.

Give it some documents, ask questions in plain English, and it finds the
answer and shows where it came from.

    from docassist import LoaderRegistry, SentenceChunker
"""

from .answers import NOT_FOUND, Answer, AnswerEngine, ExtractiveAnswerer, Source, SourceList
from .assistant import DocumentAssistant, default_loaders
from .chunking import Chunker, SentenceChunker
from .exceptions import (
    DocAssistError,
    LoaderError,
    NotFoundError,
    ProviderError,
    ValidationError,
)
from .history import Conversation, Turn
from .llm import (
    API_URL,
    DEFAULT_MODEL,
    AnthropicProvider,
    FakeProvider,
    LLMProvider,
    Message,
    post_json,
)
from .llm_answerer import SYSTEM_PROMPT, LLMAnswerer, build_prompt
from .loaders import DocumentLoader, LoaderRegistry, MarkdownLoader, TextLoader, strip_markdown
from .models import Chunk, Document, make_doc_id
from .pdf import PdfLoader
from .search import BM25Index, SearchHit, SearchIndex
from .storage import DocumentStore, MemoryStore, SqliteStore
from .text import STOP_WORDS, sentences, sentence_spans, stem, tokens

__version__ = "0.5.0"

__all__ = [
    "DocumentAssistant",
    "default_loaders",
    "Conversation",
    "Turn",
    "DocumentStore",
    "MemoryStore",
    "SqliteStore",
    "PdfLoader",
    "Answer",
    "AnswerEngine",
    "ExtractiveAnswerer",
    "Source",
    "SourceList",
    "NOT_FOUND",
    "LLMAnswerer",
    "build_prompt",
    "SYSTEM_PROMPT",
    "LLMProvider",
    "AnthropicProvider",
    "FakeProvider",
    "Message",
    "post_json",
    "API_URL",
    "DEFAULT_MODEL",
    "Document",
    "Chunk",
    "make_doc_id",
    "DocumentLoader",
    "TextLoader",
    "MarkdownLoader",
    "LoaderRegistry",
    "strip_markdown",
    "Chunker",
    "SentenceChunker",
    "SearchIndex",
    "BM25Index",
    "SearchHit",
    "tokens",
    "stem",
    "sentences",
    "sentence_spans",
    "STOP_WORDS",
    "DocAssistError",
    "LoaderError",
    "ProviderError",
    "NotFoundError",
    "ValidationError",
    "__version__",
]
