from dataclasses import dataclass
from pathlib import Path
from typing import Literal

DocumentType = Literal["TDS", "SDS"]
APPROVED_PRODUCTS = ("D.E.R. 331", "EPON Resin 8280")


@dataclass(frozen=True, slots=True)
class SourceDocument:
    path: Path
    product: str
    doc_type: DocumentType


def _document_type(path: Path) -> DocumentType:
    prefix = path.name.split("-", maxsplit=1)[0].strip().upper()
    if prefix not in {"TDS", "SDS"}:
        raise ValueError(f"PDF filename must start with TDS or SDS: {path.name}")
    return prefix  # type: ignore[return-value]


def discover_documents(
    materials_root: Path, products: list[str] | tuple[str, ...]
) -> list[SourceDocument]:
    """Discover only direct PDF children of explicitly approved product folders."""
    documents: list[SourceDocument] = []
    resolved_root = materials_root.resolve()
    for product in products:
        if product not in APPROVED_PRODUCTS:
            raise ValueError(f"Product is not approved for phase one: {product!r}")
        folder = (resolved_root / product).resolve()
        try:
            folder.relative_to(resolved_root)
        except ValueError as error:
            raise ValueError(f"Product folder is outside materials root: {folder}") from error
        if not folder.is_dir():
            raise FileNotFoundError(f"Missing product folder: {folder}")

        product_documents = [
            SourceDocument(path=path, product=product, doc_type=_document_type(path))
            for path in sorted(folder.glob("*.pdf"), key=lambda item: item.name.casefold())
        ]
        type_counts = {
            doc_type: sum(item.doc_type == doc_type for item in product_documents)
            for doc_type in ("TDS", "SDS")
        }
        if type_counts != {"TDS": 1, "SDS": 1}:
            raise ValueError(
                f"Product {product!r} must contain exactly one TDS and one SDS; "
                f"found {type_counts}"
            )
        documents.extend(product_documents)
    return documents
