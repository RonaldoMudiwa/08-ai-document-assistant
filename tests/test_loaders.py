from pathlib import Path

import pytest

from docassist import (
    DocumentLoader,
    LoaderError,
    LoaderRegistry,
    MarkdownLoader,
    TextLoader,
    strip_markdown,
)


def write(tmp_path: Path, name: str, text: str, encoding: str = "utf-8") -> Path:
    path = tmp_path / name
    path.write_text(text, encoding=encoding)
    return path


class TestTextLoader:
    def test_loads_a_text_file(self, tmp_path):
        path = write(tmp_path, "house_rules.txt", "No parties after 11pm.")
        doc = TextLoader().load(path)
        assert doc.title == "House rules"
        assert doc.text == "No parties after 11pm."
        assert doc.source == str(path)

    def test_copes_with_notepad_bom(self, tmp_path):
        path = write(tmp_path, "a.txt", "Hello", encoding="utf-8-sig")
        assert TextLoader().load(path).text == "Hello"

    def test_missing_file(self, tmp_path):
        with pytest.raises(LoaderError, match="No file"):
            TextLoader().load(tmp_path / "nope.txt")

    def test_empty_file(self, tmp_path):
        with pytest.raises(LoaderError, match="empty"):
            TextLoader().load(write(tmp_path, "a.txt", "  \n"))

    def test_not_utf8(self, tmp_path):
        path = tmp_path / "a.txt"
        path.write_bytes(b"\xff\xfe\x00bad")
        with pytest.raises(LoaderError, match="UTF-8"):
            TextLoader().load(path)

    def test_title_falls_back_to_the_file_name(self, tmp_path):
        assert TextLoader().title_for(Path("___.txt"), "x") == "___.txt"


class TestMarkdownLoader:
    def test_title_comes_from_the_first_heading(self, tmp_path):
        path = write(tmp_path, "notes.md", "# Week 3 Notes\n\nSome **bold** text.")
        doc = MarkdownLoader().load(path)
        assert doc.title == "Week 3 Notes"
        assert doc.text == "Week 3 Notes\n\nSome bold text."

    def test_no_heading_uses_the_file_name(self, tmp_path):
        doc = MarkdownLoader().load(write(tmp_path, "course-notes.md", "Just text."))
        assert doc.title == "Course notes"

    def test_strip_markdown(self):
        text = ("## Rules\n- **No** pets\n> quoted\nSee [the guide](http://x.com) and "
                "`code`.\n```\nhidden()\n```\n![logo](a.png)")
        assert strip_markdown(text) == "Rules\nNo pets\nquoted\nSee the guide and code.\n\nlogo"


class TestLoaderRegistry:
    def test_picks_the_right_loader(self, tmp_path):
        registry = LoaderRegistry()
        assert isinstance(registry.loader_for(Path("a.TXT")), TextLoader)
        assert isinstance(registry.loader_for(Path("a.md")), MarkdownLoader)

    def test_unknown_ending(self):
        with pytest.raises(LoaderError, match=r"\.docx files. Try one of: \.markdown, \.md, \.txt"):
            LoaderRegistry().loader_for("a.docx")

    def test_no_ending(self):
        with pytest.raises(LoaderError, match="no ending"):
            LoaderRegistry().loader_for("README")

    def test_load(self, tmp_path):
        doc = LoaderRegistry().load(write(tmp_path, "a.md", "# Title\nText"))
        assert doc.title == "Title"

    def test_register_a_new_loader(self, tmp_path):
        class CsvLoader(DocumentLoader):
            extensions = (".csv",)

            def read_text(self, path):
                return path.read_text().replace(",", " ")

        registry = LoaderRegistry([])
        registry.register(CsvLoader())
        assert registry.extensions == [".csv"]
        assert registry.load(write(tmp_path, "a.csv", "a,b")).text == "a b"
