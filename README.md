# AI Document Assistant

A Python program you give documents to, like a tenancy agreement or your
course notes, and then ask questions in plain English. It finds the answer
and shows which part of which document it came from.

Project 8 of a 12 week portfolio. Week 7 was about working with text and a
first machine learning model. This week builds on that with search and an
optional real AI model.

## Status

Day 5 of 7. Loaders for .txt, .md and .pdf files, overlapping chunks,
our own BM25 search index, answers that quote the best sentences with
their sources, optional answers from a real AI model (Claude), saving
everything in SQLite, and follow up questions. 160 tests.

## Putting it together

```python
from docassist import Conversation, DocumentAssistant, SqliteStore

assistant = DocumentAssistant(SqliteStore("data/documents.db"))
assistant.add_file("tenancy_agreement.md")
assistant.add_file("course_notes.pdf")

chat = Conversation()
print(assistant.ask("How much is the deposit?", chat).render())
print(assistant.ask("Is it protected?", chat).render())    # "it" = the deposit
```

`DocumentAssistant` is the front desk. You hand it files and questions,
and behind the desk it uses the loaders, the chunker, the store, the
search index and an answer engine. Every one of those is passed in (or a
sensible default is used), so any of them can be swapped. That's how the
tests run with no files and no internet.

## Getting started

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
pytest --cov
```

## Documents and chunks

A `Document` is one whole file. A `Chunk` is a small piece of it, a few
sentences long. We search chunks rather than whole documents, so an answer
can point at the exact part it came from.

Think of a big textbook. If someone asks "when is the essay due?", you
don't hand them the whole book. You point at the paragraph.

Both are frozen dataclasses that check their own values, so you can't
make a document with no text or a chunk with a negative position. A
document's id is worked out from its text, so adding the same file twice
is easy to spot.

## Reading files

```python
from docassist import LoaderRegistry

doc = LoaderRegistry().load("notes/tenancy_agreement.md")
print(doc.title, doc.word_count)
```

| Loader | Files | Title comes from |
| --- | --- | --- |
| `TextLoader` | `.txt` | The file name, tidied up |
| `MarkdownLoader` | `.md`, `.markdown` | The first `# heading`, and the markdown symbols are removed |
| `PdfLoader` | `.pdf` | The title saved inside the PDF, or the file name |

`PdfLoader` uses the pypdf library to pull the text out of each page. A
scanned PDF is just a picture of a page, with no text in it, so it gets a
clear error instead of an empty document.

Each loader is a small class behind the `DocumentLoader` base class. The
`LoaderRegistry` looks at the file's ending and passes it to the right
loader, like a post room putting letters in the right pigeonhole. A new
file type means one new class and one `register()` call. Nothing else
changes.

## Cutting documents into chunks

`SentenceChunker` groups whole sentences into chunks of about 120 words.
It never cuts a sentence in half, and it repeats the last sentence of each
chunk at the start of the next one (the overlap).

Why overlap? Imagine cutting a recipe into cards. If one step is split
across two cards, neither card makes sense alone. Overlap stops an answer
from being cut in half.

```python
from docassist import SentenceChunker

for chunk in SentenceChunker(max_words=60, overlap=1).split(doc):
    print(chunk.chunk_id, chunk.short())
```

Each chunk remembers where it starts and ends in the document, so
`doc.text[chunk.start:chunk.end]` gives its text back exactly.

## Searching

```python
from docassist import BM25Index

index = BM25Index()
index.add(SentenceChunker().split(doc))
for hit in index.search("How much is the deposit?", limit=3):
    print(f"{hit.score:.2f}", hit.matched, hit.chunk.short())
```

`BM25Index` is written from scratch, with no search library. BM25 is the
scoring method most search engines started with. For each word in the
question it asks two things:

1. **Is the word in this chunk, and how often?** More is better, but the
   fifth time counts for much less than the first. A chunk that says
   "deposit" five times isn't five times more useful.
2. **Is the word rare?** In a tenancy agreement "tenant" is everywhere, so
   it tells you very little. "deposit" only shows up in one place, so it
   points straight at the right chunk. Rare words score higher.

Long chunks are scored down a little, so they don't win just because they
contain more words.

Words are cut down before searching: "Deposits", "deposit" and "DEPOSIT"
all become `deposit`, and little words like "the" and "is" are ignored.

`SearchIndex` is the base class, so a different search method could be
swapped in later without changing anything that uses it.

## Answers with sources

```python
from docassist import ExtractiveAnswerer

question = "How much is the deposit?"
answer = ExtractiveAnswerer().answer(question, index.search(question), {doc.doc_id: doc.title})
print(answer.render())
```

```
The deposit is £1,100. [1] It is protected in a government approved deposit scheme within 30 days. [1]

Sources:
  [1] Tenancy agreement: "The deposit is £1,100. It is protected in a government approved deposit..."
```

The `ExtractiveAnswerer` never makes anything up. It goes through the
sentences in the chunks the search found, picks the ones that share the
most words with the question, and quotes them. Each one gets a number that
says where it came from. It's like a student answering with a highlighter
and page numbers instead of their own words: less smooth, but you can
always check it.

- If nothing matches, it says so: "I couldn't find anything about that in
  your documents." It doesn't guess.
- Overlapping chunks repeat sentences, so each sentence is only quoted once.
- The same chunk always keeps the same number in one answer.

`AnswerEngine` is the base class. Tomorrow a second engine plugs in that
uses a real AI model, and nothing else has to change.

## Optional: answers from a real AI model

```python
from docassist import AnthropicProvider, LLMAnswerer

engine = LLMAnswerer(AnthropicProvider.from_env())
answer = engine.answer(question, index.search(question), titles)
```

This is called **retrieval augmented generation (RAG)**: look things up
first, then write. The search finds the right chunks, and only those are
sent to the model, each with a number. The model is told to:

- use only those extracts, never outside knowledge,
- put the extract's number after every fact, like `[2]`,
- say "I couldn't find anything about that in your documents." if the
  extracts don't answer it.

It's like an open book exam. The model can word the answer nicely, but
the facts have to come from the book, with page numbers.

A few safety habits:

- **The API key comes from the `ANTHROPIC_API_KEY` environment variable.**
  It's never written in the code, saved, or printed. Even
  `repr(provider)` hides it. `.env` is in `.gitignore` too.
- **No search results means no call**, so you never pay for a question
  your documents can't answer.
- **Only the sources the model actually cited are listed**, and made up
  numbers like `[9]` are ignored.

```powershell
$env:ANTHROPIC_API_KEY = "your key here"     # Windows PowerShell, this window only
$env:DOCASSIST_MODEL = "claude-sonnet-5-5"   # optional, this is the default
```

### Plugs, so tests never go online

`LLMProvider` is the base class with one method, `complete()`. There are
two plugs:

| Provider | What it does |
| --- | --- |
| `AnthropicProvider` | Calls Anthropic's Messages API with `urllib`, no extra library. Clear errors for a bad key, no internet, or an odd reply |
| `FakeProvider` | Gives back set replies and records what it was sent. Used by every test |

Even the part that sends the web request can be swapped (`post=`), so the
tests check the exact request without ever going online, and the program
works fully offline when you don't use the AI model.

## Saving documents

`DocumentStore` is the base class, with two versions:

| Store | Keeps things | Used for |
| --- | --- | --- |
| `MemoryStore` | In a dict, gone when the program ends | Tests and the demo |
| `SqliteStore` | In a SQLite database file | Real use, so documents are still there tomorrow |

Two tables, `documents` and `chunks`. Deleting a document deletes its
chunks too (`ON DELETE CASCADE`), and adding a document with its chunks is
one transaction: all of it is saved, or none of it. Every test runs
against both stores.

The search index itself isn't saved. It's rebuilt from the saved chunks
when the program starts. That takes a moment, and it means the index can
never get out of step with the database.

## Follow up questions

If you ask "How much is the deposit?" and then "Is it protected?", the
second question doesn't say what "it" is. A `Conversation` remembers the
last few turns (5 by default):

- **For search:** a short follow up (fewer than 3 real words) is searched
  together with the question before it.
- **For the AI model:** the earlier questions and answers are sent first,
  so it knows "it" means the deposit.

It uses a `deque` with a maximum length, so the oldest turn drops off by
itself, like a queue at a till.

## Week plan

| Day | Focus |
| --- | --- |
| 1 | Documents, chunks, loaders for .txt and .md, splitting into chunks |
| 2 | Search: our own BM25 index to rank chunks for a question |
| 3 | Answers that quote the best sentences and show their sources |
| 4 | Optional real AI through an API key, plus a fake one for tests |
| 5 | Saving everything in SQLite, reading PDFs, remembering the conversation |
| 6 | Command line interface and sample documents |
| 7 | End to end tests and README |
