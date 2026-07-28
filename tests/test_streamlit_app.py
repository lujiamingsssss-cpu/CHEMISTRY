from pathlib import Path

from streamlit.testing.v1 import AppTest

from chemical_trade_copilot.inquiry_analysis import (
    InquiryAnalysis,
    KeyParameter,
    RequirementAssessment,
    SourceCitation,
)


APP = Path(__file__).parents[1] / "src" / "chemical_trade_copilot" / "streamlit_app.py"


def _supported_json() -> str:
    citation = SourceCitation(
        product="EPON Resin 8280",
        source_file="TDS - Hexion EPON Resin 8280 - Rev 2016.pdf",
        page_number=3,
    )
    analysis = InquiryAnalysis(
        summary_zh="技术条件有证据。",
        recommendation_status="supported",
        recommended_product="EPON Resin 8280",
        recommendation_reasons=("指定固化体系有证据。",),
        requirements=(
            RequirementAssessment(
                category="technical",
                requirement="MPDA HDT",
                status="supported",
                evidence=(citation,),
            ),
        ),
        key_parameters=(
            KeyParameter(
                name="Heat Deflection Temperature",
                value="156",
                unit="°C",
                conditions="Cured system",
                test_method="ASTM D648",
                curing_agent="MPDA",
                mix_ratio="100 pbw : 14.4 pbw",
                cure_schedule="2 h/80°C + 2 h/150°C",
                citation=citation,
            ),
        ),
        evidence_gaps=("Commercial facts require confirmation.",),
        source_limitations=("TDS revision is 2016.",),
        follow_up_questions=("Confirm quantity and destination.",),
        next_action="needs_commercial_input",
    )
    return analysis.model_dump_json()


def test_initial_app_is_an_english_single_inquiry_page() -> None:
    app = AppTest.from_file(str(APP)).run(timeout=30)

    assert not app.exception
    assert app.text_area[0].label == "Customer inquiry"
    assert app.button[0].label == "Analyze inquiry"
    assert "First decide what can be answered" in app.title[0].value


def test_supported_analysis_renders_product_readiness_and_editable_email() -> None:
    app = AppTest.from_file(str(APP)).run(timeout=30)
    app.session_state["analysis_json"] = _supported_json()
    app.session_state["inquiry"] = "EPON Resin 8280 with MPDA and CFR Santos"

    app.run(timeout=30)

    assert not app.exception
    assert any(header.value == "EPON Resin 8280" for header in app.header)
    assert any(
        "Technical reply ready; quotation inputs required" in item.value
        for item in app.subheader
    )
    assert any(
        area.label == "Editable English email" and "EPON Resin 8280" in area.value
        for area in app.text_area
    )
    assert all("156" not in area.value for area in app.text_area if "email" in area.label.lower())


def test_ready_to_reply_result_does_not_invent_a_quotation_workflow() -> None:
    analysis = InquiryAnalysis.model_validate_json(_supported_json())
    analysis = analysis.model_copy(
        update={
            "requirements": (analysis.requirements[0],),
            "next_action": "ready_to_reply",
        }
    )
    app = AppTest.from_file(str(APP)).run(timeout=30)
    app.session_state["analysis_json"] = analysis.model_dump_json()
    app.session_state["inquiry"] = "EPON Resin 8280 MPDA technical conditions"

    app.run(timeout=30)

    assert not app.exception
    assert all(
        item.value != "What is still needed before a quotation"
        for item in app.subheader
    )
    assert any(
        "Next action: Prepare the evidence-grounded technical reply" in item.value
        for item in app.caption
    )
