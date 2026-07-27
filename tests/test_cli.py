import pytest

from chemical_trade_copilot.cli import _parser


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
