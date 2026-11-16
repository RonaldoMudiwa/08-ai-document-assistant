import pytest

from docassist import (
    NOT_FOUND,
    Conversation,
    DocumentAssistant,
    FakeProvider,
    LLMAnswerer,
    MemoryStore,
    NotFoundError,
    SqliteStore,
    ValidationError,
)

from .conftest import PAYSLIP, TENANCY
from .pdf_maker import make_pdf


@pytest.fixture
def assistant():
    helper = DocumentAssistant()
    helper.add_text("Tenancy agreement", TENANCY)
    helper.add_text("Payslip guide", PAYSLIP)
    return helper


def test_ask(assistant):
    answer = assistant.ask("How much is the deposit?")
    assert "£1,100" in answer.text
    assert answer.sources[0].title == "Tenancy agreement"


def test_ask_something_not_in_the_documents(assistant):
    assert assistant.ask("Can I keep a helicopter?").text == NOT_FOUND


def test_empty_question(assistant):
    with pytest.raises(ValidationError):
        assistant.ask("   ")


def test_add_the_same_text_twice(assistant):
    doc, added = assistant.add_text("Copy", TENANCY)
    assert added is False
    assert doc.title == "Tenancy agreement"
    assert len(assistant.documents()) == 2


def test_add_files(tmp_path):
    (tmp_path / "rules.md").write_text("# House Rules\n\nBins go out on Monday night.")
    make_pdf(tmp_path / "gym.pdf", [["The gym opens at 6am."]])
    helper = DocumentAssistant()
    assert helper.add_file(tmp_path / "rules.md")[0].title == "House Rules"
    assert helper.add_file(tmp_path / "gym.pdf")[1] is True
    assert "6am" in helper.ask("When does the gym open?").text


def test_chunk_count(assistant):
    doc = assistant.documents()[0]
    assert assistant.chunk_count(doc.doc_id) >= 1


def test_find_by_title_or_id(assistant):
    doc = assistant.documents()[1]
    assert assistant.find("payslip GUIDE") == doc
    assert assistant.find(doc.doc_id[:6]) == doc
    assert assistant.find(doc.doc_id.upper()) == doc


@pytest.mark.parametrize("ref", ["nothing", "abc"])
def test_find_nothing(assistant, ref):
    with pytest.raises(NotFoundError, match="No document"):
        assistant.find(ref)


def test_find_more_than_one():
    helper = DocumentAssistant()
    helper.add_text("A", "one")
    helper.add_text("A", "two")
    with pytest.raises(NotFoundError, match="matches 2"):
        helper.find("A")


def test_remove(assistant):
    removed = assistant.remove("Tenancy agreement")
    assert removed.title == "Tenancy agreement"
    assert [d.title for d in assistant.documents()] == ["Payslip guide"]
    assert assistant.ask("How much is the deposit?").text == NOT_FOUND


def test_index_is_rebuilt_from_a_saved_store(tmp_path):
    path = tmp_path / "docs.db"
    with SqliteStore(path) as store:
        DocumentAssistant(store).add_text("Tenancy agreement", TENANCY)
    with SqliteStore(path) as store:
        assert "£1,100" in DocumentAssistant(store).ask("How much is the deposit?").text


def test_follow_up_questions_use_the_conversation(assistant):
    convo = Conversation()
    assistant.ask("How much is the deposit?", convo)
    follow_up = assistant.ask("Is it protected?", convo)
    assert "deposit scheme" in follow_up.text
    assert len(convo) == 2


def test_ai_engine_gets_the_history():
    fake = FakeProvider("The deposit is £1,100 [1].", "Yes, in a scheme [1].")
    helper = DocumentAssistant(MemoryStore(), engine=LLMAnswerer(fake))
    helper.add_text("Tenancy agreement", TENANCY)
    convo = Conversation()
    helper.ask("How much is the deposit?", convo)
    helper.ask("Is it protected?", convo)
    messages = fake.calls[1][1]
    assert [m.role for m in messages] == ["user", "assistant", "user"]
    assert messages[1].content == "The deposit is £1,100 [1]."


def test_bad_setting():
    with pytest.raises(ValidationError):
        DocumentAssistant(search_limit=0)
