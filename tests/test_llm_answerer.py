import pytest

from docassist import (
    NOT_FOUND,
    SYSTEM_PROMPT,
    AnswerEngine,
    Chunk,
    FakeProvider,
    LLMAnswerer,
    SearchHit,
    ValidationError,
    build_prompt,
)


def hit(doc_id, index, text):
    return SearchHit(Chunk(doc_id, index, text, 0, len(text)), 1.0)


HITS = [hit("t", 0, "The deposit is £1,100."), hit("p", 2, "Tax is taken off through PAYE."),
        hit("t", 1, "Rent is £950 a month.")]
TITLES = {"t": "Tenancy agreement", "p": "Payslip guide"}


def test_it_is_an_answer_engine():
    assert isinstance(LLMAnswerer(FakeProvider()), AnswerEngine)


def test_sends_the_numbered_extracts_and_the_rules():
    fake = FakeProvider("The deposit is £1,100 [1].")
    LLMAnswerer(fake).answer("How much is the deposit?", HITS, TITLES)
    system, messages = fake.calls[0]
    assert system == SYSTEM_PROMPT
    assert len(messages) == 1
    prompt = messages[0].content
    assert '[1] From "Tenancy agreement":\nThe deposit is £1,100.' in prompt
    assert '[2] From "Payslip guide"' in prompt
    assert prompt.endswith("Question: How much is the deposit?")


def test_only_cited_sources_are_listed():
    answer = LLMAnswerer(FakeProvider("Deposit £1,100 [1], rent £950 [3].")).answer(
        "money?", HITS, TITLES)
    assert answer.text == "Deposit £1,100 [1], rent £950 [3]."
    assert [s.number for s in answer.sources] == [1, 3]
    assert answer.sources[1].chunk_id == "t:1"


def test_made_up_source_numbers_are_ignored():
    answer = LLMAnswerer(FakeProvider("It's £1,100 [1][9].")).answer("deposit?", HITS, TITLES)
    assert [s.number for s in answer.sources] == [1]


def test_model_says_it_is_not_in_the_documents():
    answer = LLMAnswerer(FakeProvider(NOT_FOUND)).answer("pets?", HITS, TITLES)
    assert not answer.found
    assert answer.text == NOT_FOUND


def test_no_hits_means_no_call():
    fake = FakeProvider()
    assert not LLMAnswerer(fake).answer("pets?", [], TITLES).found
    assert fake.calls == []


def test_only_sends_the_best_extracts():
    fake = FakeProvider("ok [1]")
    LLMAnswerer(fake, max_extracts=1).answer("q", HITS, TITLES)
    assert "[2]" not in fake.calls[0][1][0].content


def test_unknown_title():
    assert 'From "Unknown document"' in build_prompt("q", [(1, "Unknown document", "x")])
    fake = FakeProvider("ok [1]")
    LLMAnswerer(fake).answer("q", [hit("zzz", 0, "x")], {})
    assert 'From "Unknown document"' in fake.calls[0][1][0].content


def test_bad_setting():
    with pytest.raises(ValidationError):
        LLMAnswerer(FakeProvider(), max_extracts=0)
