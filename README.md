# AI Document Assistant

A Python program you give documents to, like a tenancy agreement or your
course notes, and then ask questions in plain English. It finds the answer
and shows which part of which document it came from.

Project 8 of a 12 week portfolio. Week 7 was about working with text and a
first machine learning model. This week builds on that with search and an
optional real AI model.

## Status

Day 2 of 7. Documents and chunks, loaders for .txt and .md files,
cutting documents into overlapping chunks, and our own BM25 search index
that ranks chunks for a question. 72 tests.

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
