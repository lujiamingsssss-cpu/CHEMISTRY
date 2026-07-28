import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast

from .materials import DocumentType
from .retrieval import SearchResult


@dataclass(frozen=True, slots=True)
class RetrievalTarget:
    product: str
    source_file: str
    page_number: int


@dataclass(frozen=True, slots=True)
class GoldenRetrievalCase:
    case_id: str
    inquiry: str
    expected_targets: tuple[RetrievalTarget, ...]
    requires_insufficient_evidence: bool
    retrieval_query: str | None = None
    document_types: tuple[DocumentType, ...] | None = None


class Retriever(Protocol):
    def query(
        self,
        inquiry: str,
        *,
        limit: int,
        doc_types: tuple[DocumentType, ...] | None = None,
    ) -> list[SearchResult]: ...


@dataclass(frozen=True, slots=True)
class CaseRetrievalResult:
    case_id: str
    first_target_rank: int | None


@dataclass(frozen=True, slots=True)
class RetrievalEvaluation:
    answerable_cases: int
    hit_at_k: dict[int, float]
    cases: tuple[CaseRetrievalResult, ...]


def load_golden_cases(path: Path) -> tuple[GoldenRetrievalCase, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Golden retrieval cases must be a JSON list")

    cases: list[GoldenRetrievalCase] = []
    for raw_case in payload:
        targets = tuple(
            RetrievalTarget(
                product=str(target["product"]),
                source_file=str(target["source_file"]),
                page_number=int(target["page_number"]),
            )
            for target in raw_case["expected_targets"]
        )
        requires_insufficient_evidence = bool(
            raw_case["requires_insufficient_evidence"]
        )
        if requires_insufficient_evidence == bool(targets):
            raise ValueError(
                "A case must have either expected targets or an insufficient-evidence "
                "expectation"
            )
        cases.append(
            GoldenRetrievalCase(
                case_id=str(raw_case["id"]),
                inquiry=str(raw_case["inquiry"]),
                expected_targets=targets,
                requires_insufficient_evidence=requires_insufficient_evidence,
                retrieval_query=(
                    str(raw_case["retrieval_query"])
                    if raw_case.get("retrieval_query")
                    else None
                ),
                document_types=_load_document_types(raw_case.get("document_types")),
            )
        )
    return tuple(cases)


def evaluate_retrieval(
    cases: Sequence[GoldenRetrievalCase],
    retriever: Retriever,
    *,
    k_values: tuple[int, ...] = (1, 3, 5),
) -> RetrievalEvaluation:
    if not k_values or any(k < 1 for k in k_values):
        raise ValueError("k values must be positive integers")

    answerable = [case for case in cases if case.expected_targets]
    case_results: list[CaseRetrievalResult] = []
    for case in answerable:
        results = retriever.query(
            case.retrieval_query or case.inquiry,
            limit=max(k_values),
            doc_types=case.document_types,
        )
        rank = next(
            (
                position
                for position, result in enumerate(results, start=1)
                if _matches_any_target(result, case.expected_targets)
            ),
            None,
        )
        case_results.append(CaseRetrievalResult(case.case_id, rank))

    denominator = len(answerable)
    hit_at_k = {
        k: (
            sum(
                result.first_target_rank is not None and result.first_target_rank <= k
                for result in case_results
            )
            / denominator
            if denominator
            else 0.0
        )
        for k in k_values
    }
    return RetrievalEvaluation(
        answerable_cases=denominator,
        hit_at_k=hit_at_k,
        cases=tuple(case_results),
    )


def validate_golden_gate(
    cases: Sequence[GoldenRetrievalCase],
    retriever: Retriever,
    *,
    enabled_products: set[str],
    maximum_rank: int = 3,
) -> RetrievalEvaluation:
    applicable = tuple(case for case in cases if case.expected_targets)
    target_products = {
        target.product for case in applicable for target in case.expected_targets
    }
    disabled_targets = sorted(target_products - enabled_products)
    if disabled_targets:
        raise ValueError(
            "Positive golden target products are not enabled: "
            + ", ".join(disabled_targets)
        )
    covered_products = {
        target.product for case in applicable for target in case.expected_targets
    }
    missing = sorted(enabled_products - covered_products)
    if missing:
        raise ValueError(
            "Enabled products without a positive golden retrieval case: "
            + ", ".join(missing)
        )
    evaluation = evaluate_retrieval(
        applicable,
        retriever,
        k_values=(maximum_rank,),
    )
    failures = [
        result.case_id
        for result in evaluation.cases
        if result.first_target_rank is None or result.first_target_rank > maximum_rank
    ]
    if failures:
        raise ValueError(
            f"Golden retrieval cases missed within top {maximum_rank}: "
            + ", ".join(failures)
        )
    return evaluation


def _matches_any_target(
    result: SearchResult, targets: tuple[RetrievalTarget, ...]
) -> bool:
    return any(
        result.product == target.product
        and result.source_file == target.source_file
        and result.page_number == target.page_number
        for target in targets
    )


def _load_document_types(raw: object) -> tuple[DocumentType, ...] | None:
    if raw is None:
        return None
    if not isinstance(raw, list) or not raw:
        raise ValueError("document_types must be a non-empty JSON list")
    values = tuple(str(value).upper() for value in raw)
    if any(value not in {"TDS", "SDS"} for value in values):
        raise ValueError("document_types may contain only TDS or SDS")
    return cast(tuple[DocumentType, ...], values)
