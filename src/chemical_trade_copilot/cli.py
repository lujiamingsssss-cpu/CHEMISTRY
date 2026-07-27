import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .materials import APPROVED_PRODUCTS, discover_documents
from .pdf_pages import extract_all_pages
from .retrieval import PageIndex, SearchResult

def _result_dict(result: SearchResult) -> dict[str, Any]:
    value = asdict(result)
    value["source_path"] = str(value["source_path"])
    return value


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Page-level evidence retrieval")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest = subparsers.add_parser("ingest", help="Replace the local page index")
    ingest.add_argument("--materials-root", type=Path, required=True)
    ingest.add_argument("--database", type=Path, default=Path(".chroma"))

    query = subparsers.add_parser("query", help="Retrieve traceable source pages")
    query.add_argument("inquiry")
    query.add_argument("--database", type=Path, default=Path(".chroma"))
    query.add_argument("--limit", type=int, default=5)
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.command == "ingest":
        products = list(APPROVED_PRODUCTS)
        sources = discover_documents(args.materials_root, products)
        pages = extract_all_pages(sources)
        PageIndex(args.database).replace(pages)
        print(
            json.dumps(
                {
                    "products": products,
                    "documents": len(sources),
                    "indexed_pages": len(pages),
                },
                ensure_ascii=False,
            )
        )
        return

    results = PageIndex(args.database).query(args.inquiry, limit=args.limit)
    payload = {
        "inquiry": args.inquiry,
        "results": [_result_dict(item) for item in results],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
