import pytest

from docassist import Answer, Conversation, Message, ValidationError


def answer(question, text="Some answer."):
    return Answer(question, text)


def test_starts_empty():
    convo = Conversation()
    assert len(convo) == 0
    assert convo.messages() == []


def test_messages_alternate_user_and_assistant():
    convo = Conversation()
    convo.add(answer("How much is the deposit?", "£1,100 [1]"))
    assert convo.messages() == [Message("user", "How much is the deposit?"),
                                Message("assistant", "£1,100 [1]")]


def test_only_keeps_the_last_turns():
    convo = Conversation(max_turns=2)
    for q in ("one?", "two?", "three?"):
        convo.add(answer(q))
    assert [t.question for t in convo.turns] == ["two?", "three?"]


def test_short_follow_up_borrows_the_last_question():
    convo = Conversation()
    convo.add(answer("How much is the deposit?"))
    assert convo.search_query("When is it returned?") == "How much is the deposit? When is it returned?"


def test_full_question_is_searched_alone():
    convo = Conversation()
    convo.add(answer("How much is the deposit?"))
    question = "How much notice does the tenant give?"
    assert convo.search_query(question) == question


def test_first_question_is_searched_alone():
    assert Conversation().search_query("And then?") == "And then?"


def test_clear():
    convo = Conversation()
    convo.add(answer("q?"))
    convo.clear()
    assert len(convo) == 0


def test_bad_setting():
    with pytest.raises(ValidationError):
        Conversation(max_turns=0)
