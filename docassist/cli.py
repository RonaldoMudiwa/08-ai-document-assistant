"""The command line interface.

    python -m docassist demo                          try it with the sample documents
    python -m docassist add tenancy.md notes/         add files, or every file in a folder
    python -m docassist list                          what's been added
    python -m docassist ask "How much is the deposit?"
    python -m docassist chat                          ask one question after another
    python -m docassist remove "Tenancy Agreement"    by title or the start of its id

Add --ai before the command to have a real AI model write the answers.
Documents are saved in data/documents.db unless --db says otherwise.
"""

from __future__ import annotations

import argparse
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable, Sequence, TextIO

from .answers import Answer, AnswerEngine, ExtractiveAnswerer
from .assistant import DocumentAssistant
from .exceptions import DocAssistError
from .history import Conversation
from .llm import AnthropicProvider, LLMProvider
from .llm_answerer import LLMAnswerer
from .storage import DocumentStore, MemoryStore, SqliteStore

DEFAULT_DB = Path("data/documents.db")
SAMPLES = Path(__file__).parent / "samples"
QUIT_WORDS = {"quit", "exit", "q"}

DEMO_QUESTIONS = [
    "How much is the deposit?",
    "Is it protected?",
    "What is my tax code for?",
    "When is the coursework due?",
    "Am I allowed to have pets?",
    "What is the wifi password?",
]


class Context:
    """What a command gets to work with while it runs."""

    def __init__(self, out: TextIO, args: argparse.Namespace,
                 read_line: Callable[[str], str] = input,
                 provider_factory: Callable[[], LLMProvider] = AnthropicProvider.from_env) -> None:
        self.out = out
        self.args = args
        self.read_line = read_line
        self._provider_factory = provider_factory
        self._store: DocumentStore | None = None

    def say(self, text: str = "") -> None:
        print(text, file=self.out)

    def engine(self) -> AnswerEngine:
        """The AI model if --ai was given, otherwise the offline one."""
        if self.args.ai:
            return LLMAnswerer(self._provider_factory())
        return ExtractiveAnswerer()

    def assistant(self, store: DocumentStore | None = None) -> DocumentAssistant:
        if store is None:
            self._store = store = SqliteStore(self.args.db)
        return DocumentAssistant(store, engine=self.engine())

    def close(self) -> None:
        if isinstance(self._store, SqliteStore):
            self._store.close()


class Command(ABC):
    """One thing the user can ask for. Each command is its own small class."""

    name = ""
    help = ""

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Add this command's own options. Commands with none can skip it."""

    @abstractmethod
    def run(self, ctx: Context) -> None:
        """Do the job. Raise a DocAssistError if it can't be done."""


def files_in(paths: Sequence[Path], extensions: Sequence[str]) -> list[Path]:
    """The files given, with any folders swapped for the readable files inside them."""
    found = []
    for path in paths:
        if path.is_dir():
            found += sorted(p for p in path.rglob("*")
                            if p.is_file() and p.suffix.lower() in extensions)
        else:
            found.append(path)
    return found


class AddCommand(Command):
    name = "add"
    help = "add files, or every readable file in a folder"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("paths", nargs="+", type=Path)

    def run(self, ctx: Context) -> None:
        assistant = ctx.assistant()
        files = files_in(ctx.args.paths, assistant.loaders.extensions)
        if not files:
            raise DocAssistError("No readable files found there.")
        failed = 0
        for path in files:
            # One bad file shouldn't stop the rest from being added.
            try:
                doc, added = assistant.add_file(path)
            except DocAssistError as error:
                ctx.say(f"  Skipped {path.name}: {error}")
                failed += 1
                continue
            if added:
                ctx.say(f"  Added {doc.title} ({doc.word_count} words, "
                        f"{assistant.chunk_count(doc.doc_id)} chunks)  id {doc.doc_id}")
            else:
                ctx.say(f"  Already added: {doc.title}")
        if failed == len(files):
            raise DocAssistError("None of the files could be added.")


class ListCommand(Command):
    name = "list"
    help = "show every document that's been added"

    def run(self, ctx: Context) -> None:
        assistant = ctx.assistant()
        docs = assistant.documents()
        if not docs:
            ctx.say("No documents yet. Add some with: python -m docassist add <file>")
            return
        ctx.say(f"{'Id':<14}{'Words':>7}{'Chunks':>8}  Title")
        for doc in docs:
            ctx.say(f"{doc.doc_id:<14}{doc.word_count:>7}"
                    f"{assistant.chunk_count(doc.doc_id):>8}  {doc.title}")


class RemoveCommand(Command):
    name = "remove"
    help = "remove a document, by its title or the start of its id"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("document")

    def run(self, ctx: Context) -> None:
        doc = ctx.assistant().remove(ctx.args.document)
        ctx.say(f"Removed {doc.title}.")


class AskCommand(Command):
    name = "ask"
    help = "ask one question"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("question", nargs="+", help="the question, in quotes or not")

    def run(self, ctx: Context) -> None:
        assistant = ctx.assistant()
        if not assistant.documents():
            raise DocAssistError("Add some documents first: python -m docassist add <file>")
        show(ctx, assistant.ask(" ".join(ctx.args.question)))


class ChatCommand(Command):
    name = "chat"
    help = "ask one question after another; follow ups like 'is it...' work"

    def run(self, ctx: Context) -> None:
        assistant = ctx.assistant()
        if not assistant.documents():
            raise DocAssistError("Add some documents first: python -m docassist add <file>")
        chat(ctx, assistant)


class DemoCommand(Command):
    name = "demo"
    help = "load the sample documents in memory and ask some example questions"

    def run(self, ctx: Context) -> None:
        assistant = ctx.assistant(MemoryStore())
        for path in sorted(SAMPLES.iterdir()):
            doc, _ = assistant.add_file(path)
            ctx.say(f"Loaded {doc.title}")
        ctx.say("(These are made up example documents.)")
        conversation = Conversation()
        for question in DEMO_QUESTIONS:
            ctx.say(f"\n> {question}")
            show(ctx, assistant.ask(question, conversation))


def show(ctx: Context, answer: Answer) -> None:
    ctx.say(answer.render())


def chat(ctx: Context, assistant: DocumentAssistant) -> None:
    """Keep asking until the user types quit. 'new' starts a fresh conversation."""
    conversation = Conversation()
    ctx.say("Ask a question. Type 'new' to start over or 'quit' to stop.")
    while True:
        try:
            question = ctx.read_line("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            ctx.say()
            return
        if question.lower() in QUIT_WORDS:
            return
        if question.lower() == "new":
            conversation.clear()
            ctx.say("Starting a new conversation.")
        elif question:
            show(ctx, assistant.ask(question, conversation))


COMMANDS: tuple[Command, ...] = (
    DemoCommand(), AddCommand(), ListCommand(), AskCommand(), ChatCommand(), RemoveCommand(),
)


def build_parser(commands: Sequence[Command] = COMMANDS) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m docassist",
                                     description="Ask questions about your own documents.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB,
                        help="where documents are saved")
    parser.add_argument("--ai", action="store_true",
                        help="have a real AI model write the answers (needs ANTHROPIC_API_KEY)")
    sub = parser.add_subparsers(dest="command", metavar="command")
    for command in commands:
        child = sub.add_parser(command.name, help=command.help, description=command.help)
        command.add_arguments(child)
        child.set_defaults(handler=command)
    return parser


def main(argv: Sequence[str] | None = None, out: TextIO | None = None, *,
         read_line: Callable[[str], str] = input,
         provider_factory: Callable[[], LLMProvider] = AnthropicProvider.from_env) -> int:
    """Run one command. Returns 0 if it worked, 1 if it didn't."""
    out = out or sys.stdout
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help(out)
        return 0
    ctx = Context(out, args, read_line, provider_factory)
    try:
        args.handler.run(ctx)
    except DocAssistError as error:
        print(f"Error: {error}", file=out)
        return 1
    finally:
        ctx.close()
    return 0
