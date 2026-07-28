from pathlib import Path

import fitz
import pytest

from chemical_trade_copilot.evidence_viewer import (
    build_zoomable_page_html,
    render_citation_page,
)
from chemical_trade_copilot.inquiry_analysis import SourceCitation


def _write_pdf(path: Path, pages: int = 1) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with fitz.open() as document:
        for number in range(1, pages + 1):
            page = document.new_page()
            page.insert_text((72, 72), f"Physical page {number}")
        document.save(path)


def _materials(tmp_path: Path) -> Path:
    product = tmp_path / "EPON Resin 8280"
    _write_pdf(product / "TDS - Hexion EPON Resin 8280 - Rev 2016.pdf", pages=3)
    _write_pdf(product / "SDS - Westlake EPON Resin 8280 - US EN - 2022.pdf", pages=1)
    return tmp_path


def test_render_citation_page_uses_only_exact_approved_product_document(
    tmp_path: Path,
) -> None:
    root = _materials(tmp_path)
    citation = SourceCitation(
        product="EPON Resin 8280",
        source_file="TDS - Hexion EPON Resin 8280 - Rev 2016.pdf",
        page_number=3,
    )

    rendered = render_citation_page(citation, root)

    assert rendered.product == "EPON Resin 8280"
    assert rendered.source_file == "TDS - Hexion EPON Resin 8280 - Rev 2016.pdf"
    assert rendered.page_number == 3
    assert rendered.date_revision == "Reissued 2005 · footer revision 2016"
    assert rendered.jurisdiction == "Technical data sheet · jurisdiction not stated"
    assert rendered.png_bytes.startswith(b"\x89PNG\r\n\x1a\n")


def test_render_citation_page_rejects_unknown_file(tmp_path: Path) -> None:
    root = _materials(tmp_path)
    citation = SourceCitation(
        product="EPON Resin 8280",
        source_file="TDS - Not Approved.pdf",
        page_number=1,
    )

    with pytest.raises(ValueError, match="not an approved source document"):
        render_citation_page(citation, root)


def test_render_citation_page_rejects_page_outside_pdf(tmp_path: Path) -> None:
    root = _materials(tmp_path)
    citation = SourceCitation(
        product="EPON Resin 8280",
        source_file="TDS - Hexion EPON Resin 8280 - Rev 2016.pdf",
        page_number=4,
    )

    with pytest.raises(ValueError, match="outside the source PDF"):
        render_citation_page(citation, root)


def test_zoomable_html_has_click_and_bounded_zoom_controls() -> None:
    html = build_zoomable_page_html(
        b"\x89PNG\r\n\x1a\nimage",
        alt_text='TDS page <3> "verified"',
        source_metadata="EPON Resin 8280 · Rev 2016 · Physical page 3",
    )

    assert 'aria-label="Zoom in"' in html
    assert 'aria-label="Zoom out"' in html
    assert 'aria-label="Reset zoom"' in html
    assert 'aria-label="Open source page viewer"' in html
    assert 'data-min-zoom="50"' in html
    assert 'data-max-zoom="250"' in html
    assert 'data-zoom-step="25"' in html
    assert "image.addEventListener(\"click\"" in html
    assert "TDS page &lt;3&gt; &quot;verified&quot;" in html
    assert "EPON Resin 8280 · Rev 2016 · Physical page 3" in html
    assert "data:image/png;base64," in html
