import pytest

from docassist import Document, SentenceChunker, ValidationError


def doc_of(*sentences: str) -> Document:
    return Document.create("Doc", " ".join(sentences))


def test_every_chunk_points_back_into_the_document(tenancy):
    for chunk in SentenceChunker(max_words=20).split(tenancy):
        assert tenancy.text[chunk.start:chunk.end] == chunk.text
        assert chunk.doc_id == tenancy.doc_id


def test_short_document_is_one_chunk():
    chunks = SentenceChunker().split(doc_of("One two.", "Three four."))
    assert len(chunks) == 1
    assert chunks[0].text == "One two. Three four."


def test_chunks_stay_under_the_word_limit():
    doc = doc_of(*(f"Sentence number {i} is here." for i in range(20)))
    for chunk in SentenceChunker(max_words=12, overlap=0).split(doc):
        assert len(chunk.text.split()) <= 12


def test_overlap_repeats_the_last_sentence():
    doc = doc_of("A a a.", "B b b.", "C c c.", "D d d.")
    texts = [c.text for c in SentenceChunker(max_words=6, overlap=1).split(doc)]
    assert texts == ["A a a. B b b.", "B b b. C c c.", "C c c. D d d."]


def test_no_overlap():
    doc = doc_of("A a a.", "B b b.", "C c c.", "D d d.")
    texts = [c.text for c in SentenceChunker(max_words=6, overlap=0).split(doc)]
    assert texts == ["A a a. B b b.", "C c c. D d d."]


def test_a_very_long_sentence_gets_its_own_chunk():
    doc = doc_of("Short.", "This one is far too long for the limit.", "End.")
    texts = [c.text for c in SentenceChunker(max_words=3, overlap=1).split(doc)]
    assert texts == ["Short.", "This one is far too long for the limit.", "End."]


def test_big_overlap_still_moves_forward():
    doc = doc_of("A.", "B.", "C.")
    chunks = SentenceChunker(max_words=2, overlap=5).split(doc)
    assert [c.index for c in chunks] == [0, 1]
    assert chunks[-1].text.endswith("C.")


@pytest.mark.parametrize("max_words,overlap", [(0, 1), (10, -1)])
def test_bad_settings(max_words, overlap):
    with pytest.raises(ValidationError):
        SentenceChunker(max_words, overlap)
