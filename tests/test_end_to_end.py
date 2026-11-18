"""Whole journeys through the program, the way a person would use it.

Each test drives the real command line with a real database file. Only the
AI model is faked, so nothing goes online.
"""

import io

import pytest

from docassist import NOT_FOUND, DocumentAssistant, FakeProvider, SqliteStore, __version__
from docassist.cli import SAMPLES, main

from .pdf_maker import make_pdf


def run(*argv, **options):
    out = io.StringIO()
    code = main(list(argv), out, **options)
    return code, out.getvalue()


@pytest.fixture
def folder(tmp_path):
    docs = tmp_path / "my documents"
    docs.mkdir()
    for sample in SAMPLES.iterdir():
        (docs / sample.name).write_text(sample.read_text(encoding="utf-8"), encoding="utf-8")
    make_pdf(docs / "gym_membership.pdf",
             [["Gym Membership Terms."],
              ["The membership costs 30 pounds a month.", "You can cancel with one month notice."]],
             title="Gym Membership Terms")
    return docs


def test_version():
    assert __version__ == "1.0.0"


def test_add_ask_restart_remove(tmp_path, folder):
    db = str(tmp_path / "data" / "documents.db")

    code, out = run("--db", db, "add", str(folder))
    assert code == 0
    assert out.count("Added") == 4

    # A fresh run reads everything back from the database file.
    code, out = run("--db", db, "list")
    assert {"Tenancy Agreement", "Payslip guide", "Programming Module Notes",
            "Gym Membership Terms"} <= set(line.split("  ")[-1] for line in out.splitlines()[1:])

    code, out = run("--db", db, "ask", "How much does the gym membership cost?")
    assert "30 pounds a month" in out
    assert "[1] Gym Membership Terms" in out

    code, out = run("--db", db, "ask", "When are office hours?")
    assert "Tuesdays from 2pm to 4pm" in out

    code, out = run("--db", db, "remove", "Gym Membership Terms")
    assert code == 0
    code, out = run("--db", db, "ask", "How much does the gym membership cost?")
    assert "30 pounds" not in out


def test_adding_the_same_folder_again_adds_nothing(tmp_path, folder):
    db = str(tmp_path / "documents.db")
    run("--db", db, "add", str(folder))
    code, out = run("--db", db, "add", str(folder))
    assert out.count("Already added") == 4
    with SqliteStore(db) as store:
        assert len(store) == 4


def test_a_chat_with_follow_ups(tmp_path, folder):
    db = str(tmp_path / "documents.db")
    run("--db", db, "add", str(folder))
    typed = iter(["How much is the deposit?", "Is it protected?", "What is the wifi password?",
                  "quit"])
    code, out = run("--db", db, "chat", read_line=lambda prompt: next(typed))
    assert code == 0
    assert "The deposit is £1,100. [1]" in out
    assert "tenancy deposit scheme" in out
    assert NOT_FOUND in out


def test_ai_answers_from_start_to_finish(tmp_path, folder):
    db = str(tmp_path / "documents.db")
    run("--db", db, "add", str(folder))
    fake = FakeProvider("The rent is £950 per month [1], paid by standing order [1].",
                        NOT_FOUND)
    typed = iter(["How much is the rent?", "Who won the football?", "quit"])
    code, out = run("--db", db, "--ai", "chat", read_line=lambda prompt: next(typed),
                    provider_factory=lambda: fake)
    assert code == 0
    assert "The rent is £950 per month [1]" in out
    assert "[1] Tenancy Agreement" in out
    # The model was only ever shown extracts from the documents.
    first_prompt = fake.calls[0][1][-1].content
    assert first_prompt.startswith("Extracts:")
    assert "The rent is £950 per month." in first_prompt
    # The second question also carried the first turn, so follow ups would work.
    assert [m.role for m in fake.calls[1][1]] == ["user", "assistant", "user"]


def test_the_python_way_matches_the_command_line(tmp_path, folder):
    with SqliteStore(tmp_path / "documents.db") as store:
        assistant = DocumentAssistant(store)
        for path in sorted(folder.iterdir()):
            assistant.add_file(path)
        answer = assistant.ask("What is the pass mark?")
    code, out = run("--db", str(tmp_path / "documents.db"), "ask", "What is the pass mark?")
    assert answer.render() in out
