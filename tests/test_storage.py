import pytest

from docassist import DocumentStore, MemoryStore, SentenceChunker, SqliteStore


@pytest.fixture(params=["memory", "sqlite"])
def store(request, tmp_path):
    if request.param == "memory":
        yield MemoryStore()
    else:
        with SqliteStore(tmp_path / "sub" / "docs.db") as s:
            yield s


def chunks_of(doc):
    return SentenceChunker(max_words=20).split(doc)


def test_it_is_a_document_store(store):
    assert isinstance(store, DocumentStore)


def test_add_and_get(store, tenancy):
    assert store.add(tenancy, chunks_of(tenancy)) is True
    assert store.get(tenancy.doc_id) == tenancy
    assert store.get("nope") is None


def test_adding_twice_is_refused(store, tenancy):
    store.add(tenancy, chunks_of(tenancy))
    assert store.add(tenancy, chunks_of(tenancy)) is False
    assert len(store) == 1


def test_documents_in_the_order_added(store, tenancy, payslip):
    store.add(payslip, chunks_of(payslip))
    store.add(tenancy, chunks_of(tenancy))
    assert [d.title for d in store] == ["Payslip guide", "Tenancy agreement"]


def test_chunks_come_back_the_same(store, tenancy, payslip):
    store.add(tenancy, chunks_of(tenancy))
    store.add(payslip, chunks_of(payslip))
    assert store.chunks(tenancy.doc_id) == chunks_of(tenancy)
    assert len(store.chunks()) == len(chunks_of(tenancy)) + len(chunks_of(payslip))
    assert store.chunks("nope") == []


def test_remove_takes_the_chunks_too(store, tenancy, payslip):
    store.add(tenancy, chunks_of(tenancy))
    store.add(payslip, chunks_of(payslip))
    assert store.remove(tenancy.doc_id) is True
    assert store.get(tenancy.doc_id) is None
    assert store.chunks(tenancy.doc_id) == []
    assert store.chunks() == chunks_of(payslip)
    assert store.remove(tenancy.doc_id) is False


def test_sqlite_keeps_documents_between_runs(tmp_path, tenancy):
    path = tmp_path / "docs.db"
    with SqliteStore(path) as first:
        first.add(tenancy, chunks_of(tenancy))
    with SqliteStore(path) as second:
        assert second.get(tenancy.doc_id) == tenancy
        assert second.chunks(tenancy.doc_id) == chunks_of(tenancy)


def test_sqlite_in_memory(tenancy):
    store = SqliteStore()
    store.add(tenancy, chunks_of(tenancy))
    assert len(store) == 1
    store.close()
