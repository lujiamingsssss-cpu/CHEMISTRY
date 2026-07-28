from pathlib import Path

import pytest

from chemical_trade_copilot.cli import _parser, _result_dict
from chemical_trade_copilot.retrieval import SearchResult


def test_ingest_cli_does_not_allow_product_override() -> None:
    parser = _parser()

    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "ingest",
                "--materials-root",
                "G:/materials",
                "--product",
                "Unreviewed Product",
            ]
        )


def test_analyze_cli_ranks_three_pages_by_default() -> None:
    args = _parser().parse_args(["analyze", "customer inquiry"])

    assert args.command == "analyze"
    assert args.inquiry == "customer inquiry"
    assert args.limit == 3


def test_query_result_json_keeps_full_page_text_internal() -> None:
    result = SearchResult(
        text="matched chunk",
        product="EPON Resin 8280",
        doc_type="TDS",
        source_file="TDS.pdf",
        source_path=Path("C:/TDS.pdf"),
        page_number=3,
        distance=0.1,
        page_text="full physical page",
    )

    payload = _result_dict(result)

    assert payload["text"] == "matched chunk"
    assert "page_text" not in payload
