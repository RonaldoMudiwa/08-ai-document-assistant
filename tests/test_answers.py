import pytest

from docassist import (
    NOT_FOUND,
    Answer,
    AnswerEngine,
    BM25Index,
    Chunk,
    ExtractiveAnswerer,
    SearchHit,
    SentenceChunker,
    Source,
    ValidationError,
)


@pytest.fixture
def setup(tenancy, payslip):
    index = BM25Index()
    for doc in (tenancy, payslip):
        index.add(SentenceChunker(max_words=30).split(doc))
    titles = {tenancy.doc_id: tenancy.title, payslip.doc_id: payslip.title}
    return index, titles


def ask(setup, question, **options):
    index, titles = setup
    return ExtractiveAnswerer(**options).answer(question, index.search(question), titles)


def hit(doc_id, index, text, score=1.0):
    return SearchHit(Chunk(doc_id, index, text, 0, len(text)), score)


def test_it_is_an_answer_engine():
    assert isinstance(ExtractiveAnswerer(), AnswerEngine)


def test_quotes_the_right_sentence_with_a_source(setup):
    answer = ask(setup, "How much is the deposit?")
    assert answer.found
    assert answer.text.startswith("The deposit is £1,100. [1]")
    assert answer.sources[0].title == "Tenancy agreement"
    assert answer.sources[0].number == 1


def test_best_matching_sentence_comes_first(setup):
    answer = ask(setup, "How much notice must the tenant give?", max_sentences=1)
    assert answer.text == ("The tenant must give two months notice in writing to end the "
                           "tenancy. [1]")


def test_sources_from_two_documents(setup):
    answer = ask(setup, "monthly pension rent", max_sentences=3)
    titles = {s.title for s in answer.sources}
    assert titles == {"Tenancy agreement", "Payslip guide"}
    assert [s.number for s in answer.sources] == list(range(1, len(answer.sources) + 1))


def test_nothing_found(setup):
    answer = ask(setup, "Can I keep a helicopter?")
    assert not answer.found
    assert answer.text == NOT_FOUND
    assert answer.render() == NOT_FOUND


def test_no_hits_at_all():
    assert ExtractiveAnswerer().answer("rent?", [], {}) == Answer.not_found("rent?")


def test_repeated_sentences_from_overlapping_chunks_appear_once():
    hits = [hit("d", 0, "Rent is due. Bins go out Monday."),
            hit("d", 1, "Bins go out Monday. Rent goes up in May.")]
    answer = ExtractiveAnswerer(max_sentences=5).answer("rent bins", hits, {"d": "House"})
    assert answer.text.count("Bins go out Monday.") == 1


def test_same_chunk_gets_the_same_number():
    hits = [hit("d", 0, "Rent is due on Monday. Rent is £500.")]
    answer = ExtractiveAnswerer().answer("rent", hits, {"d": "House"})
    assert answer.text == "Rent is due on Monday. [1] Rent is £500. [1]"
    assert len(answer.sources) == 1


def test_unknown_title():
    answer = ExtractiveAnswerer().answer("rent", [hit("x", 0, "Rent.")], {})
    assert answer.sources[0].title == "Unknown document"


def test_render_lists_the_sources(setup):
    text = ask(setup, "How much is the deposit?", max_sentences=1).render()
    lines = text.splitlines()
    assert lines[0] == "The deposit is £1,100. [1]"
    assert lines[2] == "Sources:"
    assert lines[3].startswith('  [1] Tenancy agreement: "')


def test_source_label():
    source = Source(2, "d", "Notes", "d:0", "Some text")
    assert source.label() == '[2] Notes: "Some text"'


def test_bad_setting():
    with pytest.raises(ValidationError):
        ExtractiveAnswerer(max_sentences=0)
