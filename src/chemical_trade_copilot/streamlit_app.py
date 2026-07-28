import html
import os
from collections.abc import Sequence
from pathlib import Path

import streamlit as st

from chemical_trade_copilot.evidence_viewer import (
    build_zoomable_page_html,
    render_citation_page,
)
from chemical_trade_copilot.inquiry_analysis import (
    DeepSeekInquiryAnalyzer,
    DeepSeekJsonClient,
    InquiryAnalysis,
    InquiryRetrievalPlanner,
)
from chemical_trade_copilot.materials import (
    evidence_scope_caption,
    load_material_catalog,
    material_catalog_fingerprint,
)
from chemical_trade_copilot.retrieval import PageIndex
from chemical_trade_copilot.ui_components import APP_CSS, build_copy_button_html
from chemical_trade_copilot.ui_presenter import (
    build_analysis_view,
    build_email_draft,
)
from chemical_trade_copilot.workflow import analyze_inquiry


DEFAULT_MATERIALS_ROOT = Path(r"G:\桌面\化工")
DEFAULT_DATABASE = Path(".chroma")
DEFAULT_MATERIAL_CATALOG = Path("materials_catalog.json")


class _MetadataOnlyEmbedder:
    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        raise RuntimeError("Evidence generation checks must not calculate embeddings")


def _material_catalog_path() -> Path:
    return Path(
        os.environ.get(
            "CHEMICAL_TRADE_MATERIAL_CATALOG", str(DEFAULT_MATERIAL_CATALOG)
        )
    )


def _current_evidence_fingerprint() -> str:
    expected = material_catalog_fingerprint(
        load_material_catalog(_material_catalog_path())
    )
    with PageIndex(
        Path(os.environ.get("CHEMICAL_TRADE_DATABASE", str(DEFAULT_DATABASE))),
        embedder=_MetadataOnlyEmbedder(),
    ) as index:
        index.assert_catalog_fingerprint(expected)
    return expected


def _run_analysis(inquiry: str) -> tuple[InquiryAnalysis, str]:
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise ValueError("DEEPSEEK_API_KEY is not available in this process")
    client = DeepSeekJsonClient(
        api_key,
        base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        model=os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-pro"),
    )
    expected_fingerprint = material_catalog_fingerprint(
        load_material_catalog(_material_catalog_path())
    )
    with PageIndex(
        Path(os.environ.get("CHEMICAL_TRADE_DATABASE", str(DEFAULT_DATABASE)))
    ) as index:
        index.assert_catalog_fingerprint(expected_fingerprint)
        analysis = analyze_inquiry(
            inquiry,
            index=index,
            planner=InquiryRetrievalPlanner(client),
            analyzer=DeepSeekInquiryAnalyzer(client),
            limit=3,
        )
    return analysis, expected_fingerprint


def _render_decision_line(analysis: InquiryAnalysis) -> None:
    view = build_analysis_view(analysis)
    statuses = (
        ("Technical", view.technical_status, analysis.recommendation_status == "supported"),
        ("Compliance", view.compliance_status, False),
        ("Quotation", view.quotation_status, False),
        ("Logistics", view.logistics_status, False),
    )
    cells = "".join(
        (
            '<div class="ctc-decision">'
            f'<span><i class="ctc-dot{"" if ready else " open"}"></i>'
            f"{html.escape(label)}</span>"
            f"<b>{html.escape(status)}</b></div>"
        )
        for label, status, ready in statuses
    )
    st.html(f'<div class="ctc-decision-line">{cells}</div>')


def _render_verified_parameters(analysis: InquiryAnalysis) -> None:
    if not analysis.key_parameters:
        return
    st.subheader("Why the technical conclusion holds")
    st.write(
        "The approved technical source contains a test result for the specified "
        "cured system with its formulation, curing, and test conditions bound together."
    )
    for parameter in analysis.key_parameters:
        first = (
            f"{html.escape(parameter.curing_agent or 'Not stated')} · "
            f"{html.escape(parameter.mix_ratio or 'Not stated')}"
        )
        second = html.escape(parameter.cure_schedule or "Not stated")
        third = (
            f'<span class="number">{html.escape(parameter.value)}'
            f"{html.escape(parameter.unit)}</span> · {html.escape(parameter.test_method)}"
        )
        citation = parameter.citation
        st.html(
            '<div class="ctc-fact">'
            '<div class="ctc-fact-head"><span>Verified fact · specified cured system</span>'
            '<span>Not a continuous-use temperature</span></div>'
            '<div class="ctc-fact-grid">'
            f'<div class="ctc-fact-cell"><b>{first}</b>Curing agent and mix ratio</div>'
            f'<div class="ctc-fact-cell"><b>{second}</b>Cure schedule</div>'
            f'<div class="ctc-fact-cell"><b>{third}</b>{html.escape(parameter.name)}</div>'
            '</div><div class="ctc-source">'
            f"<span>{html.escape(citation.source_file)} · physical page "
            f"{citation.page_number}</span><b>Verified source</b></div></div>"
        )
    st.html(
        '<div class="ctc-warning">Document age, revision, and jurisdiction remain '
        "material limitations. A cured-system HDT result must not be presented as "
        "uncured-resin performance or continuous-use temperature.</div>"
    )


def _render_sources(analysis: InquiryAnalysis) -> None:
    view = build_analysis_view(analysis)
    if not view.citations:
        return
    st.subheader("Inspect the source page")
    st.caption(
        "Click the authentic PDF page to open the viewer. Use Zoom in, Zoom out, "
        "Reset, or click the enlarged page to toggle between fit and 150%."
    )
    materials_root = Path(
        os.environ.get("CHEMICAL_TRADE_MATERIALS_ROOT", str(DEFAULT_MATERIALS_ROOT))
    )
    catalog_path = _material_catalog_path()
    for citation in view.citations:
        try:
            rendered = render_citation_page(citation, materials_root, catalog_path)
        except (FileNotFoundError, ValueError) as error:
            st.warning(f"The approved source page could not be rendered: {error}")
            continue
        st.markdown(
            f"**{rendered.source_file}**  \n"
            f"{rendered.product} · Physical page {rendered.page_number} · "
            f"{rendered.date_revision} · {rendered.jurisdiction}"
        )
        alt_text = (
            f"{rendered.product}, {rendered.source_file}, "
            f"physical page {rendered.page_number}"
        )
        source_metadata = (
            f"{rendered.product} · {rendered.source_file} · Physical page "
            f"{rendered.page_number} · {rendered.date_revision} · "
            f"{rendered.jurisdiction}"
        )
        st.html(
            build_zoomable_page_html(
                rendered.png_bytes,
                alt_text=alt_text,
                source_metadata=source_metadata,
            ),
            unsafe_allow_javascript=True,
        )


def _render_readiness(analysis: InquiryAnalysis) -> None:
    view = build_analysis_view(analysis)
    st.subheader("What is still needed before a quotation")
    customer, internal = st.columns(2, gap="large")
    with customer:
        st.markdown("**Confirm with the customer**")
        items = "".join(
            f"<li>{html.escape(question)}</li>" for question in view.customer_questions
        )
        st.html(f'<ul class="ctc-checklist">{items}</ul>')
    with internal:
        st.markdown("**Confirm internally**")
        st.html(
            '<ul class="ctc-checklist"><li>Stock, MOQ, and available quantity</li>'
            "<li>Price, currency, and quotation validity</li>"
            "<li>Freight and estimated shipping date</li>"
            "<li>Payment terms and packaging availability</li></ul>"
        )
    st.markdown("**Document pack**")
    st.caption(
        "TDS: available · SDS: available, jurisdiction-specific · COA: not supplied "
        "and batch-specific · Destination-market documents: confirm when required"
    )


def _render_email(analysis: InquiryAnalysis) -> None:
    draft = build_email_draft(analysis)
    st.subheader("Editable English reply")
    st.caption(
        "Review and edit before copying. The app does not connect to an inbox or "
        "send messages."
    )
    email_key = f"email_draft_{analysis.recommendation_status}"
    st.text_area(
        "Editable English email",
        value=draft.body,
        height=310,
        key=email_key,
    )
    st.html(build_copy_button_html(), unsafe_allow_javascript=True)


def _render_supported(analysis: InquiryAnalysis) -> None:
    view = build_analysis_view(analysis)
    st.html('<div class="ctc-eyebrow">Evidence validated</div>')
    st.header(analysis.recommended_product or "Supported technical result")
    st.subheader(view.headline)
    st.write(
        "A technical reply can be prepared from the approved evidence. Commercial, "
        "compliance, and logistics facts still require separate confirmation."
    )
    _render_decision_line(analysis)
    if view.open_items:
        st.caption(f"Open items: {' · '.join(view.open_items)}")
    st.caption(f"Next action: {view.next_action}")
    st.divider()
    _render_verified_parameters(analysis)
    if analysis.next_action == "needs_commercial_input":
        st.divider()
        _render_readiness(analysis)
    st.divider()
    _render_sources(analysis)
    st.divider()
    _render_email(analysis)


def _render_insufficient(analysis: InquiryAnalysis) -> None:
    view = build_analysis_view(analysis)
    if view.fail_closed:
        st.html(
            '<div class="ctc-guardrail"><b>Safe fallback applied.</b> The model output '
            "did not pass local evidence validation, so its product conclusions and "
            "technical values were not used.</div>"
        )
    st.html('<div class="ctc-eyebrow">Current evidence is insufficient</div>')
    st.header("No product can be recommended yet")
    st.subheader(view.headline)
    st.write(
        "The approved documents do not establish the decisive technical or regulatory "
        "conditions needed for this request. No product or unverified value is shown."
    )
    _render_decision_line(analysis)
    if view.open_items:
        st.caption(f"Open items: {' · '.join(view.open_items)}")
    st.caption(f"Next action: {view.next_action}")
    st.divider()
    st.subheader("Collect the information that changes the decision")
    questions = view.customer_questions or (
        "Which additional approved technical evidence can be supplied?",
    )
    st.markdown("\n".join(f"- {question}" for question in questions))
    st.divider()
    _render_email(analysis)


def _render_entry() -> None:
    st.html('<div class="ctc-eyebrow">Inquiry → Evidence → Reply</div>')
    st.title("First decide what can be answered. Then prepare the right reply.")
    st.write(
        "Paste a Chinese or English customer inquiry. The app separates technical, "
        "compliance, commercial, and logistics requests and recommends a product only "
        "when the approved documents support it."
    )
    st.text_area(
        "Customer inquiry",
        key="inquiry",
        height=190,
        placeholder=(
            "Example: Please confirm the MPDA-cured EPON Resin 8280 test conditions, "
            "and quote CFR Santos for 5 metric tons."
        ),
    )
    st.caption(
        "Helpful details: final application, key performance requirement, destination "
        "country or port, quantity, delivery window, Incoterm, packaging, and "
        "certification needs. Missing details can be identified during analysis."
    )
    if st.button("Analyze inquiry", type="primary"):
        inquiry = st.session_state.get("inquiry", "")
        if not inquiry.strip():
            st.error("Enter a customer inquiry before starting the analysis.")
            return
        try:
            with st.spinner("Validating technical documents and evidence guardrails..."):
                analysis, fingerprint = _run_analysis(inquiry)
        except Exception:
            st.error(
                "The analysis could not be completed safely. Check the local API and "
                "index configuration, then try again. No unsupported result was shown."
            )
            return
        st.session_state["analysis_json"] = analysis.model_dump_json()
        st.session_state["analysis_catalog_fingerprint"] = fingerprint
        for key in tuple(st.session_state):
            if str(key).startswith("email_draft_"):
                del st.session_state[key]
        st.rerun()


def main() -> None:
    st.set_page_config(
        page_title="Chemical Trade Copilot",
        page_icon="⚗",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    st.html(APP_CSS)
    st.caption("CHEMICAL TRADE COPILOT · APPROVED TDS/SDS EVIDENCE")
    payload = st.session_state.get("analysis_json")
    if payload:
        try:
            current_fingerprint = _current_evidence_fingerprint()
        except (FileNotFoundError, ValueError):
            st.session_state.pop("analysis_json", None)
            st.session_state.pop("analysis_catalog_fingerprint", None)
            st.error(
                "The approved catalog and evidence index are not synchronized. "
                "The cached result was cleared."
            )
            _render_entry()
            return
        if st.session_state.get("analysis_catalog_fingerprint") != current_fingerprint:
            st.session_state.pop("analysis_json", None)
            st.session_state.pop("analysis_catalog_fingerprint", None)
            st.warning(
                "This result no longer matches the approved evidence generation and "
                "was cleared. Analyze the inquiry again."
            )
            _render_entry()
            return
    if not payload:
        _render_entry()
        st.caption(
            f"Private Demo · {evidence_scope_caption(_material_catalog_path())} · "
            "No automatic email sending"
        )
        return
    if st.button("Start a new inquiry"):
        st.session_state.pop("analysis_json", None)
        st.session_state.pop("analysis_catalog_fingerprint", None)
        st.session_state["inquiry"] = ""
        for key in tuple(st.session_state):
            if str(key).startswith("email_draft_"):
                del st.session_state[key]
        st.rerun()
    analysis = InquiryAnalysis.model_validate_json(payload)
    if analysis.recommendation_status == "supported":
        _render_supported(analysis)
    else:
        _render_insufficient(analysis)
    st.divider()
    st.caption(evidence_scope_caption(_material_catalog_path()))


main()
