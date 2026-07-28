import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

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


class Retriever(Protocol):
    def query(self, inquiry: str, *, limit: int) -> list[SearchResult]: ...


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
        results = retriever.query(case.inquiry, limit=max(k_values))
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


def _matches_any_target(
    result: SearchResult, targets: tuple[RetrievalTarget, ...]
) -> bool:
    return any(
        result.product == target.product
        and result.source_file == target.source_file
        and result.page_number == target.page_number
        for target in targets
    )
