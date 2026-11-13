import pytest

from docassist import BM25Index, Chunk, SearchIndex, SentenceChunker, ValidationError


def chunk(doc_id: str, index: int, text: str) -> Chunk:
    return Chunk(doc_id, index, text, 0, len(text))


@pytest.fixture
def index(tenancy, payslip) -> BM25Index:
    idx = BM25Index()
    chunker = SentenceChunker(max_words=30)
    idx.add(chunker.split(tenancy))
    idx.add(chunker.split(payslip))
    return idx


def test_it_is_a_search_index():
    assert isinstance(BM25Index(), SearchIndex)


def test_finds_the_right_chunk(index, tenancy):
    best = index.search("How much is the deposit?")[0]
    assert best.chunk.doc_id == tenancy.doc_id
    assert "£1,100" in best.chunk.text
    assert best.matched == ("deposit",)


def test_finds_the_right_document(index, payslip):
    assert index.search("what is national insurance")[0].chunk.doc_id == payslip.doc_id


def test_best_first_and_limited(index):
    hits = index.search("notice tenant landlord month", limit=2)
    assert len(hits) == 2
    assert hits[0].score >= hits[1].score


def test_no_matching_words_means_no_hits(index):
    assert index.search("helicopter") == []


def test_only_stop_words_means_no_hits(index):
    assert index.search("what is the") == []


def test_empty_index():
    assert BM25Index().search("anything") == []


def test_rare_words_count_more():
    idx = BM25Index()
    idx.add([chunk("d", 0, "rent rent deposit"), chunk("d", 1, "rent paid monthly"),
             chunk("d", 2, "rent is due")])
    assert idx.idf("deposit") > idx.idf("rent")
    assert idx.idf("rent") >= 0


def test_repeating_a_word_helps_less_each_time():
    idx = BM25Index(b=0)
    idx.add([chunk("d", 0, "fee"), chunk("d", 1, "fee fee"), chunk("d", 2, "fee fee fee fee"),
             chunk("d", 3, "other")])
    one, two, four = (idx.search("fee", 3)[i].score for i in (2, 1, 0))
    assert two - one > four - two > 0


def test_long_chunks_are_scored_down():
    idx = BM25Index()
    idx.add([chunk("d", 0, "pets allowed"),
             chunk("d", 1, "pets " + "garden kitchen bedroom window door " * 4)])
    hits = idx.search("pets")
    assert hits[0].chunk.index == 0


def test_ties_keep_chunk_order():
    idx = BM25Index()
    idx.add([chunk("d", 1, "boiler"), chunk("d", 0, "boiler"), chunk("e", 0, "other")])
    assert [h.chunk.index for h in idx.search("boiler")] == [0, 1]


def test_adding_the_same_chunk_replaces_it():
    idx = BM25Index()
    idx.add([chunk("d", 0, "old words")])
    idx.add([chunk("d", 0, "new words")])
    assert len(idx) == 1
    assert idx.search("old") == []
    assert idx.search("new")[0].chunk.text == "new words"


def test_remove_document(index, tenancy):
    before = len(index)
    removed = index.remove_document(tenancy.doc_id)
    assert removed > 0
    assert len(index) == before - removed
    assert index.search("deposit") == []
    assert f"{tenancy.doc_id}:0" not in index


def test_remove_unknown_document(index):
    assert index.remove_document("nope") == 0


@pytest.mark.parametrize("k1,b", [(-1, 0.5), (1.5, -0.1), (1.5, 1.1)])
def test_bad_settings(k1, b):
    with pytest.raises(ValidationError):
        BM25Index(k1, b)


def test_bad_limit(index):
    with pytest.raises(ValidationError):
        index.search("rent", limit=0)
