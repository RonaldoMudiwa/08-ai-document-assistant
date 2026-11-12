import pytest

from docassist import STOP_WORDS, sentences, sentence_spans, stem, tokens


@pytest.mark.parametrize("word,expected", [
    ("payments", "payment"),
    ("policies", "policy"),
    ("address", "address"),
    ("bus", "bus"),
    ("is", "is"),
    ("tax", "tax"),
    ("this", "this"),
])
def test_stem(word, expected):
    assert stem(word) == expected


def test_tokens_lower_case_and_drop_stop_words():
    assert tokens("The Deposits are PROTECTED") == ["deposit", "protected"]


def test_tokens_can_keep_stop_words():
    assert tokens("Is it not late?", keep_stop_words=True) == ["is", "it", "not", "late"]


def test_tokens_join_apostrophes():
    assert tokens("the tenant's rent") == ["tenant", "rent"]


def test_tokens_keep_numbers():
    assert tokens("£950 per month") == ["950", "per", "month"]


def test_stop_words_are_lower_case():
    assert all(w == w.lower() for w in STOP_WORDS)


def test_sentences_split_on_full_stops_and_blank_lines():
    text = "First one. Second one!\n\nA heading\nThird? Yes."
    assert sentences(text) == ["First one.", "Second one!", "A heading Third?", "Yes."]


def test_sentence_spans_point_back_into_the_text():
    text = "  Hello there.   Bye now.  "
    assert [text[s:e] for s, e in sentence_spans(text)] == ["Hello there.", "Bye now."]


def test_trailing_space_is_trimmed():
    assert sentences("no full stop   ") == ["no full stop"]


def test_blank_text_has_no_sentences():
    assert sentences("   \n\n  ") == []
