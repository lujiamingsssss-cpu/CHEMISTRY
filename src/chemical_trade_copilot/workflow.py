from typing import Protocol

from .inquiry_analysis import (
    EvidencePage,
    InquiryAnalysis,
    RetrievalPlan,
    merge_ranked_with_corpus,
)
from .materials import DocumentType
from .pdf_pages import PageRecord
from .retrieval import SearchResult


class RetrievalPlanner(Protocol):
    def plan(self, inquiry: str) -> RetrievalPlan: ...


class EvidenceIndex(Protocol):
    def query(
        self,
        inquiry: str,
        *,
        limit: int,
        doc_types: tuple[DocumentType, ...],
    ) -> list[SearchResult]: ...

    def pages(
        self, *, doc_types: tuple[DocumentType, ...]
    ) -> list[PageRecord]: ...


class InquiryAnalyzer(Protocol):
    def analyze(
        self, inquiry: str, evidence: list[EvidencePage]
    ) -> InquiryAnalysis: ...


def analyze_inquiry(
    inquiry: str,
    *,
    index: EvidenceIndex,
    planner: RetrievalPlanner,
    analyzer: InquiryAnalyzer,
    limit: int = 3,
) -> InquiryAnalysis:
    plan = planner.plan(inquiry)
    ranked = index.query(
        plan.search_query,
        limit=limit,
        doc_types=plan.document_types,
    )
    evidence = merge_ranked_with_corpus(
        ranked, index.pages(doc_types=plan.document_types)
    )
    return analyzer.analyze(inquiry, evidence)
