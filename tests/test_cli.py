import io

import pytest

from docassist import FakeProvider, ProviderError
from docassist.cli import COMMANDS, SAMPLES, build_parser, files_in, main


def run(*argv, read_line=None, provider=None):
    out = io.StringIO()
    options = {}
    if read_line is not None:
        options["read_line"] = read_line
    if provider is not None:
        options["provider_factory"] = lambda: provider
    code = main(list(argv), out, **options)
    return code, out.getvalue()


@pytest.fixture
def db(tmp_path):
    return str(tmp_path / "docs.db")


@pytest.fixture
def docs(tmp_path):
    folder = tmp_path / "docs"
    folder.mkdir()
    (folder / "rules.md").write_text("# House Rules\n\nBins go out on Monday night.")
    (folder / "gym.txt").write_text("The gym opens at 6am on weekdays.")
    (folder / "photo.jpg").write_bytes(b"not a document")
    return folder


def lines_of(*answers):
    """Turns a list of replies into a read_line function, like someone typing."""
    replies = iter(answers)

    def read_line(prompt):
        try:
            return next(replies)
        except StopIteration:
            raise EOFError from None
    return read_line


def test_no_command_shows_help():
    code, out = run()
    assert code == 0
    assert "usage: python -m docassist" in out


def test_every_command_has_a_name_and_help():
    for command in COMMANDS:
        assert command.name and command.help
    assert "demo" in build_parser().format_help()


def test_files_in_expands_folders(docs):
    found = files_in([docs, docs / "gym.txt"], [".md", ".txt"])
    assert [p.name for p in found] == ["gym.txt", "rules.md", "gym.txt"]


def test_add_a_folder_then_list(db, docs):
    code, out = run("--db", db, "add", str(docs))
    assert code == 0
    assert "Added House Rules" in out
    assert "Added Gym" in out
    assert "photo" not in out
    code, out = run("--db", db, "list")
    assert "House Rules" in out and "Gym" in out
    assert out.splitlines()[0].startswith("Id")


def test_adding_twice(db, docs):
    run("--db", db, "add", str(docs / "gym.txt"))
    assert "Already added: Gym" in run("--db", db, "add", str(docs / "gym.txt"))[1]


def test_a_bad_file_is_skipped_but_the_rest_are_added(db, docs, tmp_path):
    empty = tmp_path / "empty.txt"
    empty.write_text("")
    code, out = run("--db", db, "add", str(empty), str(docs / "gym.txt"))
    assert code == 0
    assert "Skipped empty.txt" in out
    assert "Added Gym" in out


def test_every_file_bad(db, tmp_path):
    bad = tmp_path / "a.docx"
    bad.write_text("x")
    code, out = run("--db", db, "add", str(bad))
    assert code == 1
    assert "Error: None of the files could be added." in out


def test_empty_folder(db, tmp_path):
    code, out = run("--db", db, "add", str(tmp_path))
    assert code == 1
    assert "No readable files" in out


def test_list_when_empty(db):
    assert "No documents yet" in run("--db", db, "list")[1]


def test_ask(db, docs):
    run("--db", db, "add", str(docs))
    code, out = run("--db", db, "ask", "When", "does", "the", "gym", "open?")
    assert code == 0
    assert "The gym opens at 6am on weekdays. [1]" in out
    assert "Sources:" in out


def test_ask_with_no_documents(db):
    code, out = run("--db", db, "ask", "anything?")
    assert code == 1
    assert "Add some documents first" in out


def test_ask_with_ai(db, docs):
    run("--db", db, "add", str(docs))
    fake = FakeProvider("It opens at 6am [1].")
    code, out = run("--db", db, "--ai", "ask", "When does the gym open?", provider=fake)
    assert code == 0
    assert "It opens at 6am [1]." in out
    assert len(fake.calls) == 1


def test_ai_without_a_key(db, docs):
    run("--db", db, "add", str(docs))

    def no_key():
        raise ProviderError("Set the ANTHROPIC_API_KEY environment variable")

    out = io.StringIO()
    assert main(["--db", db, "--ai", "ask", "gym?"], out, provider_factory=no_key) == 1
    assert "ANTHROPIC_API_KEY" in out.getvalue()


def test_remove(db, docs):
    run("--db", db, "add", str(docs))
    code, out = run("--db", db, "remove", "house rules")
    assert code == 0
    assert "Removed House Rules." in out
    assert "House Rules" not in run("--db", db, "list")[1]


def test_remove_unknown(db):
    code, out = run("--db", db, "remove", "nothing")
    assert code == 1
    assert "Error: No document called 'nothing'." in out


def test_chat(db, docs):
    run("--db", db, "add", str(docs))
    code, out = run("--db", db, "chat",
                    read_line=lines_of("When does the gym open?", "", "new", "bins?", "quit"))
    assert code == 0
    assert "6am" in out
    assert "Starting a new conversation." in out
    assert "Monday night" in out


def test_chat_ends_on_ctrl_d(db, docs):
    run("--db", db, "add", str(docs))
    code, _ = run("--db", db, "chat", read_line=lines_of("gym?"))
    assert code == 0


def test_chat_with_no_documents(db):
    assert run("--db", db, "chat", read_line=lines_of())[0] == 1


def test_demo_uses_the_samples_and_saves_nothing(db, tmp_path):
    code, out = run("--db", db, "demo")
    assert code == 0
    assert "made up example documents" in out
    assert "The deposit is £1,100. [1]" in out
    assert "Pets are not allowed without written permission" in out
    assert "I couldn't find anything about that" in out
    assert not (tmp_path / "docs.db").exists()


def test_samples_are_there():
    assert sorted(p.name for p in SAMPLES.iterdir()) == [
        "course_notes.md", "payslip_guide.txt", "tenancy_agreement.md"]
