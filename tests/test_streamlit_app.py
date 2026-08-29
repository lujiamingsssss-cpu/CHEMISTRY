from collections.abc import Sequence
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from chemical_trade_copilot.inquiry_analysis import (
    InquiryAnalysis,
    KeyParameter,
    RequirementAssessment,
    SourceCitation,
)
from chemical_trade_copilot.materials import (
    evidence_scope_caption,
    load_material_catalog,
    material_catalog_fingerprint,
)
from chemical_trade_copilot.pdf_pages import PageRecord
from chemical_trade_copilot.retrieval import PageIndex


APP = Path(__file__).parents[1] / "src" / "chemical_trade_copilot" / "streamlit_app.py"
CATALOG = Path(__file__).parents[1] / "materials_catalog.json"


class _FixtureEmbedder:
    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]


@pytest.fixture(autouse=True)
def isolated_catalog_generation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    database = tmp_path / "chroma"
    with PageIndex(database, embedder=_FixtureEmbedder()) as index:
        index.replace(
            [
                PageRecord(
                    text="fixture evidence",
                    product="EPON Resin 8280",
                    doc_type="TDS",
                    source_file="fixture.pdf",
                    source_path=tmp_path / "fixture.pdf",
                    page_number=1,
                )
            ],
            catalog_fingerprint=_current_fingerprint(),
        )
    monkeypatch.setenv("CHEMICAL_TRADE_DATABASE", str(database))
    monkeypatch.setenv("CHEMICAL_TRADE_MATERIAL_CATALOG", str(CATALOG))


def _current_fingerprint() -> str:
    return material_catalog_fingerprint(load_material_catalog(CATALOG))


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


def test_evidence_scope_caption_reads_enabled_products_from_catalog(
    tmp_path: Path,
) -> None:
    catalog = tmp_path / "catalog.json"
    catalog.write_text(
        """[
          {"product":"Product B","relative_path":"B/TDS.pdf","document_type":"TDS","date_revision":"2026","jurisdiction":"US","enabled":true,"sha256":"0000000000000000000000000000000000000000000000000000000000000000","source_url":"https://example.com/b","acquired_on":"2026-07-28"},
          {"product":"Product A","relative_path":"A/TDS.pdf","document_type":"TDS","date_revision":"2026","jurisdiction":"US","enabled":true,"sha256":"1111111111111111111111111111111111111111111111111111111111111111","source_url":"https://example.com/a","acquired_on":"2026-07-28"},
          {"product":"Old Product","relative_path":"Old/TDS.pdf","document_type":"TDS","date_revision":"2020","jurisdiction":"US","enabled":false,"sha256":"2222222222222222222222222222222222222222222222222222222222222222","source_url":"https://example.com/old","acquired_on":"2026-07-28"}
        ]""",
        encoding="utf-8",
    )

    caption = evidence_scope_caption(catalog)

    assert "Product A and Product B" in caption
    assert "Old Product" not in caption


def test_supported_analysis_renders_product_readiness_and_editable_email() -> None:
    app = AppTest.from_file(str(APP)).run(timeout=30)
    app.session_state["analysis_json"] = _supported_json()
    app.session_state["analysis_catalog_fingerprint"] = _current_fingerprint()
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
    app.session_state["analysis_catalog_fingerprint"] = _current_fingerprint()
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


def test_cached_analysis_is_cleared_when_catalog_generation_changes() -> None:
    app = AppTest.from_file(str(APP)).run(timeout=30)
    app.session_state["analysis_json"] = _supported_json()
    app.session_state["analysis_catalog_fingerprint"] = "stale"

    app.run(timeout=30)

    assert not app.exception
    assert "analysis_json" not in app.session_state
    assert all(header.value != "EPON Resin 8280" for header in app.header)
    assert any("no longer matches" in warning.value for warning in app.warning)
