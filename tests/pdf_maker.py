"""Makes small real PDF files for the tests, so we don't need any saved in the repo."""

from __future__ import annotations

from pathlib import Path


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def make_pdf(path: Path, pages: list[list[str]], title: str | None = None) -> Path:
    """Write a PDF with one page per list of lines. A page with no lines is blank."""
    objects: list[str] = []
    page_ids = [3 + i * 2 for i in range(len(pages))]
    font_id = 3 + len(pages) * 2
    info_id = font_id + 1
    objects.append("<< /Type /Catalog /Pages 2 0 R >>")
    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>")
    for lines, pid in zip(pages, page_ids):
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                       f"/Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {pid + 1} 0 R >>")
        ops = "".join(f"BT /F1 12 Tf 72 {720 - i * 20} Td ({_escape(line)}) Tj ET\n"
                      for i, line in enumerate(lines))
        objects.append(f"<< /Length {len(ops.encode('latin-1'))} >>\nstream\n{ops}endstream")
    objects.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    objects.append(f"<< /Title ({_escape(title)}) >>" if title else "<< >>")

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n{body}\nendobj\n".encode("latin-1")
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R /Info {info_id} 0 R >>\n"
            f"startxref\n{xref}\n%%EOF\n").encode()
    path.write_bytes(bytes(out))
    return path
