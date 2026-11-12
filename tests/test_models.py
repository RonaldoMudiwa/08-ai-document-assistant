import pytest

from docassist import Chunk, Document, ValidationError, make_doc_id


class TestDocument:
    def test_create_gives_an_id_from_the_text(self):
        doc = Document.create("Notes", "Some text here.")
        assert doc.doc_id == make_doc_id("Some text here.")
        assert len(doc.doc_id) == 12

    def test_same_text_same_id_different_text_different_id(self):
        assert make_doc_id("a") == make_doc_id("a")
        assert make_doc_id("a") != make_doc_id("b")

    def test_title_is_tidied(self):
        assert Document.create("  Notes  ", "text").title == "Notes"

    def test_word_count(self):
        assert Document.create("Notes", "one two  three\nfour").word_count == 4

    @pytest.mark.parametrize("doc_id,title,text", [
        ("", "Notes", "text"),
        ("abc", "  ", "text"),
        ("abc", "Notes", "   \n"),
    ])
    def test_bad_values_are_refused(self, doc_id, title, text):
        with pytest.raises(ValidationError):
            Document(doc_id, title, text)

    def test_it_cannot_be_changed(self):
        doc = Document.create("Notes", "text")
        with pytest.raises(AttributeError):
            doc.title = "Other"


class TestChunk:
    def test_chunk_id_joins_document_and_index(self):
        assert Chunk("abc", 3, "Hello.", 0, 6).chunk_id == "abc:3"

    @pytest.mark.parametrize("index,text,start,end", [
        (-1, "Hi", 0, 2),
        (0, " ", 0, 1),
        (0, "Hi", 5, 5),
        (0, "Hi", -1, 2),
    ])
    def test_bad_values_are_refused(self, index, text, start, end):
        with pytest.raises(ValidationError):
            Chunk("abc", index, text, start, end)

    def test_short_keeps_short_text(self):
        assert Chunk("a", 0, "Hello\n  there.", 0, 14).short() == "Hello there."

    def test_short_cuts_long_text(self):
        chunk = Chunk("a", 0, "word " * 40, 0, 200)
        short = chunk.short(20)
        assert len(short) <= 20
        assert short.endswith("...")
