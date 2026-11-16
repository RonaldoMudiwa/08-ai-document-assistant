import pytest

from docassist import LoaderError, PdfLoader, default_loaders

from .pdf_maker import make_pdf


def test_reads_every_page(tmp_path):
    path = make_pdf(tmp_path / "course_notes.pdf",
                    [["Week one covers loops."], [], ["Week two covers classes."]])
    doc = PdfLoader().load(path)
    assert doc.text == "Week one covers loops.\n\nWeek two covers classes."
    assert doc.title == "Course notes"
    assert doc.source == str(path)


def test_title_from_inside_the_pdf(tmp_path):
    path = make_pdf(tmp_path / "scan001.pdf", [["Hello there."]], title="Staff Handbook")
    assert PdfLoader().load(path).title == "Staff Handbook"


def test_read_text(tmp_path):
    path = make_pdf(tmp_path / "a.pdf", [["Just this."]])
    assert PdfLoader().read_text(path) == "Just this."


def test_no_text_in_it(tmp_path):
    path = make_pdf(tmp_path / "scan.pdf", [[]])
    with pytest.raises(LoaderError, match="scanned picture"):
        PdfLoader().load(path)


def test_not_really_a_pdf(tmp_path):
    path = tmp_path / "fake.pdf"
    path.write_text("this is not a pdf")
    with pytest.raises(LoaderError, match="couldn't be read as a PDF"):
        PdfLoader().load(path)


def test_missing_file(tmp_path):
    with pytest.raises(LoaderError, match="No file"):
        PdfLoader().load(tmp_path / "nope.pdf")


def test_default_loaders_include_pdf():
    assert ".pdf" in default_loaders().extensions
