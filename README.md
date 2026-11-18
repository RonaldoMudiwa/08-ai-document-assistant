# AI Document Assistant

A Python program you give documents to, like a tenancy agreement or your
course notes, and then ask questions in plain English. It finds the answer
and shows which part of which document it came from.

Project 8 of a 12 week portfolio. Week 7 was about working with text and a
first machine learning model. This week builds on that with search and an
optional real AI model.

## Status

Finished. Reads .txt, .md and .pdf files, cuts them into overlapping
chunks, searches them with our own BM25 index, and answers by quoting the
best sentences with their sources. Can optionally have a real AI model
(Claude) write the answers from the same sources. Saves everything in
SQLite, understands follow up questions, and has a command line with a
demo. 188 tests with 100% coverage. Version 1.0.0.

## The idea

Think of a librarian who has read all your paperwork. You ask "how much
notice do I have to give?" and they don't hand you the whole tenancy
agreement. They open it at the right page, read you the line, and show you
where it is so you can check. That's what this program does.

## Getting started

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
pytest --cov
```

## Using it

```bash
python -m docassist demo                          # try it with the sample documents
python -m docassist add tenancy.md notes/         # add files, or every file in a folder
python -m docassist list                          # what's been added
python -m docassist ask How much is the deposit?
python -m docassist chat                          # one question after another
python -m docassist remove "Tenancy Agreement"    # by title or the start of its id
python -m docassist --ai ask "Can I end the tenancy early?"   # a real AI model writes it
```

```
> How much is the deposit?
The deposit is £1,100. [1] It is protected in a government approved tenancy deposit scheme within 30 days of being paid. [1] ...

> Is it protected?
It is protected in a government approved tenancy deposit scheme within 30 days of being paid. [1]

> What is the wifi password?
I couldn't find anything about that in your documents.
```

| Command | What it does |
| --- | --- |
| `demo` | Loads the three sample documents in memory and asks some example questions. Saves nothing |
| `add <files or folders>` | Adds documents. Folders are searched for .txt, .md and .pdf files. A bad file is skipped and the rest still go in |
| `list` | Every document with its id, word count and number of chunks |
| `ask <question>` | Answers one question, with sources |
| `chat` | Keeps asking until you type `quit`. Follow ups like "is it protected?" work. `new` starts over |
| `remove <title or id>` | Removes a document and its chunks |

`--db` picks another database file (default `data/documents.db`) and
`--ai` uses the AI model instead of the offline answers.

The sample documents in `docassist/samples/` (a tenancy agreement, a
payslip guide and some course notes) are **made up**. The names, address
and amounts aren't real.

Each command is its own small class with a `name`, `help` and `run`, the
same Command pattern as the last few weeks. `main()` returns 0 or 1 and
prints `Error: ...` for anything that goes wrong, instead of a crash.

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
The deposit is £1,100. [1] It is protected in a government approved tenancy deposit scheme within 30 days of being paid. [1] The deposit is returned within 10 days of the end of the tenancy, minus any agreed deductions for damage or unpaid rent. [2]

Sources:
  [1] Tenancy Agreement: "The deposit is £1,100."
  [2] Tenancy Agreement: "The deposit is returned within 10 days of the end of the tenancy, minus any a..."
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
- Headings like "Deposit" aren't sentences, so they're never quoted.
- Each source shows the sentence that was quoted, so you can find it.

`AnswerEngine` is the base class. The AI answers below are a second engine
that plugs into the same place, so nothing else had to change.

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
one transaction: all of it is saved, or none of it. Every storage
test runs against both stores.

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

## What it can't do

Being honest about the limits matters as much as the features:

- **The offline answers match words, not meaning.** Ask "Can I keep a
  cat?" and it quotes the payslip guide ("Keep them for at least a
  year...") instead of the line about pets, because it doesn't
  know a cat is a pet. "Am I allowed to have pets?" works, because it uses
  the same words as the document. With `--ai`, the model won't pass off an
  unrelated sentence as an answer, but it can still only use what the
  search found.
- **The word cutting is rough.** "policies" becomes "policy", but
  "running" doesn't become "run".
- **Scanned PDFs can't be read.** They're pictures, so there's no text.
  That would need OCR (reading text from pictures).
- **The AI answers haven't been tried live yet.** The tests check the
  exact request with a fake. The first real run needs my own API key.

## How it's built

```
            cli.py  (Command classes: demo, add, list, ask, chat, remove)
               |
        DocumentAssistant  (the front desk)
     /       |        |          \            \
LoaderRegistry  Chunker  DocumentStore  SearchIndex   AnswerEngine
 TextLoader   Sentence-  MemoryStore    BM25Index     ExtractiveAnswerer
 MarkdownLoader Chunker  SqliteStore                  LLMAnswerer
 PdfLoader                                                 |
                                                      LLMProvider
                                                 AnthropicProvider, FakeProvider
```

- **Abstract base classes as plugs:** `DocumentLoader`, `Chunker`,
  `DocumentStore`, `SearchIndex`, `AnswerEngine` and `LLMProvider`. Each
  has more than one version, and the rest of the program only talks to the
  base class.
- **Dependency injection:** the assistant is handed its store, index,
  chunker, loaders and engine, and the CLI is handed how to read typed
  lines and how to make the AI provider. That's why every test runs with
  no internet and no typing.
- **Strategy pattern:** offline or AI answers, memory or SQLite storage,
  chosen when the program starts.
- **Registry:** `LoaderRegistry` picks a loader by file ending, and new
  ones can be registered.
- **Command pattern** for the command line, like the last few weeks.
- **Frozen dataclasses** (`Document`, `Chunk`, `SearchHit`, `Answer`,
  `Source`, `Message`) that check their own values and can't change.
- **One error family:** everything raises a `DocAssistError`, so the
  command line can show `Error: ...` instead of crashing.

## Project layout

```
docassist/
    models.py        Document and Chunk
    loaders.py       DocumentLoader, TextLoader, MarkdownLoader, LoaderRegistry
    pdf.py           PdfLoader
    text.py          words, stop words, sentences
    chunking.py      Chunker, SentenceChunker
    search.py        SearchIndex, BM25Index, SearchHit
    answers.py       AnswerEngine, ExtractiveAnswerer, Answer, Source
    llm.py           LLMProvider, AnthropicProvider, FakeProvider, Message
    llm_answerer.py  LLMAnswerer and the prompt
    storage.py       DocumentStore, MemoryStore, SqliteStore
    history.py       Conversation
    assistant.py     DocumentAssistant
    cli.py           the command line
    exceptions.py    DocAssistError and friends
    samples/         three made up documents for the demo
tests/               one test file per module, plus end to end tests
    pdf_maker.py     builds small real PDFs for the tests
```

## Tests

```bash
pytest --cov
```

188 tests, 100% line and branch coverage. `.coveragerc` makes the run
fail if coverage drops below 95%.

- No test goes online. The AI model is a `FakeProvider`, and even the web
  request itself is swapped for a fake that records what would be sent.
- The PDF tests build small real PDFs while they run, so no PDFs are kept
  in the repo.
- The end to end tests drive the real command line with a real database
  file: add a folder, restart, ask, chat with follow ups, remove.
- Writing the tests found real problems: after a document was removed,
  "How much is the deposit?" still got an answer from the payslip guide
  just because both used the word "much". Question words like "much" and
  "many" are now ignored. Running the demo showed headings being quoted as
  answers, so those are skipped now too.

## What I learned this week

- **How search engines rank results** with BM25, and why rare words matter
  more than common ones.
- **Retrieval augmented generation (RAG):** search first, then let a model
  write only from what was found, with sources. This is how most real
  "chat with your documents" tools work.
- **Calling an AI API safely:** keys from environment variables, never in
  code; hiding the key from `repr`; not paying for questions that can't be
  answered; checking the sources the model gives back.
- **Testing code that talks to the internet** by putting the network
  behind a plug and using fakes.
- **Reading PDFs**, and why scanned ones have no text.
- **Remembering a conversation** with a `deque`, so follow ups work.
- **Being honest about limits.** Matching words isn't the same as
  understanding meaning, and the README says so.

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
