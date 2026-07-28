from pathlib import Path

import fitz

from chemical_trade_copilot.materials import SourceDocument
from chemical_trade_copilot.pdf_pages import extract_pages


def _write_pdf(path: Path) -> None:
    document = fitz.open()
    first = document.new_page()
    first.insert_text((72, 72), "EPON Resin 8280 high solids coatings")
    document.new_page()  # Deliberately blank; page numbering must remain physical.
    third = document.new_page()
    third.insert_text((72, 72), "Heat Deflection Temperature 156 C")
    document.save(path)
    document.close()


def test_extract_pages_preserves_physical_page_and_source_metadata(tmp_path: Path) -> None:
    path = tmp_path / "TDS - EPON Resin 8280.pdf"
    _write_pdf(path)
    source = SourceDocument(
        path=path,
        product="EPON Resin 8280",
        doc_type="TDS",
        date_revision="2016",
        jurisdiction="Technical data sheet · jurisdiction not stated",
        sha256="0" * 64,
        source_url="https://manufacturer.example/tds.pdf",
        acquired_on="2026-07-28",
    )

    pages = extract_pages(source)

    assert [page.page_number for page in pages] == [1, 3]
    assert pages[0].source_file == path.name
    assert pages[0].product == "EPON Resin 8280"
    assert pages[0].doc_type == "TDS"
    assert "high solids coatings" in pages[0].text
    assert "156 C" in pages[1].text
