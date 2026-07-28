from pathlib import Path

from chemical_trade_copilot.evaluation import (
    GoldenRetrievalCase,
    RetrievalTarget,
    evaluate_retrieval,
    load_golden_cases,
)
from chemical_trade_copilot.retrieval import SearchResult


FIXTURE = Path(__file__).parent / "fixtures" / "golden_retrieval_cases.json"


def test_golden_cases_fix_products_files_pages_and_unsupported_case() -> None:
    cases = load_golden_cases(FIXTURE)

    assert len(cases) == 5
    assert [case.case_id for case in cases] == [
        "epon_high_solids_en",
        "epon_mpda_hdt_en",
        "der_protective_coatings_zh",
        "der_formulated_hdt_zh",
        "unsupported_continuous_service_temperature_zh",
    ]
    assert all(case.expected_targets for case in cases[:4])
    assert all(
        target.source_file.startswith("TDS - ")
        and target.page_number in {1, 2, 3}
        for case in cases[:4]
        for target in case.expected_targets
    )
    assert cases[-1].expected_targets == ()
    assert cases[-1].requires_insufficient_evidence is True


class StubRetriever:
    def query(self, inquiry: str, *, limit: int) -> list[SearchResult]:
        if inquiry == "case-one":
            return [
                _result("wrong.pdf", 9),
                _result("target-one.pdf", 1),
            ][:limit]
        return [_result("wrong.pdf", 9)][:limit]


def _result(source_file: str, page_number: int) -> SearchResult:
    return SearchResult(
        text="evidence",
        product="Product",
        doc_type="TDS",
        source_file=source_file,
        source_path=Path(f"C:/{source_file}"),
        page_number=page_number,
        distance=0.1,
    )


def test_evaluate_retrieval_reports_rank_and_hit_at_k_for_answerable_cases() -> None:
    cases = (
        GoldenRetrievalCase(
            case_id="one",
            inquiry="case-one",
            expected_targets=(RetrievalTarget("Product", "target-one.pdf", 1),),
            requires_insufficient_evidence=False,
        ),
        GoldenRetrievalCase(
            case_id="two",
            inquiry="case-two",
            expected_targets=(RetrievalTarget("Product", "target-two.pdf", 2),),
            requires_insufficient_evidence=False,
        ),
        GoldenRetrievalCase(
            case_id="unsupported",
            inquiry="unsupported",
            expected_targets=(),
            requires_insufficient_evidence=True,
        ),
    )

    evaluation = evaluate_retrieval(cases, StubRetriever(), k_values=(1, 3, 5))

    assert evaluation.answerable_cases == 2
    assert evaluation.hit_at_k == {1: 0.0, 3: 0.5, 5: 0.5}
    assert [(result.case_id, result.first_target_rank) for result in evaluation.cases] == [
        ("one", 2),
        ("two", None),
    ]
