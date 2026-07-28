import argparse
import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .materials import APPROVED_PRODUCTS, discover_documents
from .pdf_pages import extract_all_pages
from .inquiry_analysis import (
    DeepSeekInquiryAnalyzer,
    DeepSeekJsonClient,
    InquiryRetrievalPlanner,
    merge_ranked_with_corpus,
)
from .retrieval import PageIndex, SearchResult

def _result_dict(result: SearchResult) -> dict[str, Any]:
    value = asdict(result)
    value.pop("page_text", None)
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

    analyze = subparsers.add_parser(
        "analyze", help="Create a cited chemical export inquiry analysis"
    )
    analyze.add_argument("inquiry")
    analyze.add_argument("--database", type=Path, default=Path(".chroma"))
    analyze.add_argument("--limit", type=int, default=3)
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

    if args.command == "query":
        results = PageIndex(args.database).query(args.inquiry, limit=args.limit)
        payload = {
            "inquiry": args.inquiry,
            "results": [_result_dict(item) for item in results],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise SystemExit("DEEPSEEK_API_KEY must be set in the process environment")
    client = DeepSeekJsonClient(
        api_key,
        base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        model=os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-pro"),
    )
    index = PageIndex(args.database)
    plan = InquiryRetrievalPlanner(client).plan(args.inquiry)
    ranked = index.query(
        plan.search_query,
        limit=args.limit,
        doc_types=plan.document_types,
    )
    evidence = merge_ranked_with_corpus(
        ranked, index.pages(doc_types=plan.document_types)
    )
    analysis = DeepSeekInquiryAnalyzer(client).analyze(args.inquiry, evidence)
    print(analysis.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
