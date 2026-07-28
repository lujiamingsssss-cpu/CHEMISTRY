from dataclasses import dataclass

from .inquiry_analysis import InquiryAnalysis, SourceCitation


@dataclass(frozen=True, slots=True)
class EmailDraft:
    subject: str
    body: str


@dataclass(frozen=True, slots=True)
class AnalysisView:
    headline: str
    technical_status: str
    compliance_status: str
    quotation_status: str
    logistics_status: str
    citations: tuple[SourceCitation, ...]
    fail_closed: bool


def build_email_draft(analysis: InquiryAnalysis) -> EmailDraft:
    if analysis.recommendation_status == "supported":
        product = analysis.recommended_product
        if product is None:
            raise ValueError("A supported analysis requires a product")
        return EmailDraft(
            subject=f"Technical follow-up — {product}",
            body=(
                "Dear [Customer name],\n\n"
                f"Thank you for your inquiry regarding {product}. Based on the "
                "technical documents currently available, the specified cured-system "
                "test result is supported under the documented formulation, curing, "
                "and test conditions.\n\n"
                "To prepare an accurate commercial response, please confirm your "
                "required quantity, preferred delivery window, destination port, "
                "preferred Incoterm, packaging requirement, final application, and "
                "any target-country certification requirements.\n\n"
                "Stock, MOQ, price, freight, lead time, and regulatory suitability "
                "remain subject to separate confirmation.\n\n"
                "Best regards,\n[Name]"
            ),
        )
    return EmailDraft(
        subject="Additional technical information required",
        body=(
            "Dear [Customer name],\n\n"
            "Thank you for your inquiry. The currently approved technical documents "
            "do not provide enough evidence to confirm a suitable product for the "
            "requested conditions.\n\n"
            "Please confirm the final application, target country and applicable "
            "regulatory standard, whether the operating condition is continuous or "
            "intermittent, the exposure medium, and the required service duration.\n\n"
            "We will review the request again after the relevant technical or supplier "
            "documentation is available.\n\n"
            "Best regards,\n[Name]"
        ),
    )


def build_analysis_view(analysis: InquiryAnalysis) -> AnalysisView:
    citations = _unique_citations(analysis)
    fail_closed = _is_fail_closed(analysis)
    if analysis.recommendation_status == "supported":
        return AnalysisView(
            headline="Technical reply ready; quotation inputs required",
            technical_status="Ready to reply",
            compliance_status="Confirm target-market requirements",
            quotation_status="Internal inputs required",
            logistics_status="Shipping inputs required",
            citations=citations,
            fail_closed=fail_closed,
        )
    return AnalysisView(
        headline="More evidence is required before recommending a product",
        technical_status="More evidence required",
        compliance_status="Confirm target-market requirements",
        quotation_status="Do not quote yet",
        logistics_status="Confirm after technical fit",
        citations=citations,
        fail_closed=fail_closed,
    )


def _unique_citations(analysis: InquiryAnalysis) -> tuple[SourceCitation, ...]:
    ordered = [
        citation
        for requirement in analysis.requirements
        for citation in requirement.evidence
    ] + [parameter.citation for parameter in analysis.key_parameters]
    unique: list[SourceCitation] = []
    seen: set[tuple[str, str, int]] = set()
    for citation in ordered:
        identity = (citation.product, citation.source_file, citation.page_number)
        if identity in seen:
            continue
        seen.add(identity)
        unique.append(citation)
    return tuple(unique)


def _is_fail_closed(analysis: InquiryAnalysis) -> bool:
    narrative = " ".join(
        (*analysis.recommendation_reasons, *analysis.evidence_gaps)
    ).casefold()
    return any(
        marker in narrative
        for marker in (
            "未通过本地证据校验",
            "local evidence validation",
        )
    )
