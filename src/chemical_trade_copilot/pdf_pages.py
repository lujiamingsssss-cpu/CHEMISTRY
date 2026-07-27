from dataclasses import dataclass
from pathlib import Path

import fitz

from .materials import DocumentType, SourceDocument


@dataclass(frozen=True, slots=True)
class PageRecord:
    text: str
    product: str
    doc_type: DocumentType
    source_file: str
    source_path: Path
    page_number: int


def extract_pages(source: SourceDocument) -> list[PageRecord]:
    """Extract non-empty pages while retaining the PDF's physical page number."""
    records: list[PageRecord] = []
    with fitz.open(source.path) as document:
        for zero_based_page, page in enumerate(document):
            text = page.get_text("text", sort=True).strip()
            if not text:
                continue
            records.append(
                PageRecord(
                    text=text,
                    product=source.product,
                    doc_type=source.doc_type,
                    source_file=source.path.name,
                    source_path=source.path.resolve(),
                    page_number=zero_based_page + 1,
                )
            )
    return records


def extract_all_pages(sources: list[SourceDocument]) -> list[PageRecord]:
    return [page for source in sources for page in extract_pages(source)]
