import hashlib
import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
ROOT = REPO / "output" / "twinkle-stage5-formal-model-motion-candidates"
CONTRACT = ROOT / "work" / "two-component-asset-contract.json"
REFERENCE = ROOT / "evidence" / "approved-complete-explanation-reference.png"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _contract() -> dict:
    assert CONTRACT.is_file(), "two-component formal model asset contract is missing"
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def test_contract_is_locked_without_authorizing_render_or_integration():
    contract = _contract()

    assert contract["schema"] == "twinkle-stage5-two-component-model-motion-asset-contract-v1"
    assert contract["status"] == "locked-contract-only"
    assert contract["scope"] == "two-component-complete-explanation-carriers"
    assert contract["authorization"] == {
        "contractWriteAuthorized": True,
        "blenderRenderAuthorized": False,
        "completeSequenceGenerationAuthorized": False,
        "formalAssetMigrationAuthorized": False,
        "registryModificationAuthorized": False,
        "manifestModificationAuthorized": False,
        "homepageModificationAuthorized": False,
        "h2IntegrationAuthorized": False,
        "viewportLockAuthorized": False,
        "commitPushPrDeployAuthorized": False,
    }


def test_contract_binds_approved_visual_and_source_authorities():
    contract = _contract()
    authority = contract["authority"]
    visual = contract["approval"]["visualTarget"]

    assert REFERENCE.is_file()
    assert visual["path"] == REFERENCE.relative_to(REPO).as_posix()
    assert visual["sha256"] == _sha256(REFERENCE)
    assert visual["dimensions"] == [1950, 1230]
    assert authority["candidateBlend"]["sha256"] == (
        "584EBB7F8F5F5CAEB7AF469DBF02A465DE7016D67A9D64539A018E9F6DDD4FD6"
    )
    assert authority["v18Prototype"]["sha256"] == (
        "5B8332F02749307222F27674BAC61BCCB4091FF39574547CD1A30876FFDC5296"
    )
    assert authority["fullQualityManifest"]["sha256"] == (
        "A915F285DCD45DCF086CAE4EBCA8B085C7BC27D500F2A3CEB6BC788099D3AB3D"
    )
    assert authority["rgbaFamilyEvidence"]["sha256"] == (
        "111D91F6977CDFB996C6DCFA09FFACDB6E6F065D2692F55CCA1970E85B6159ED"
    )


def test_contract_locks_layers_motion_and_visual_relationships():
    contract = _contract()
    composition = contract["composition"]
    motion = contract["motion"]

    assert composition["background"] == {
        "independent": True,
        "fixed": True,
        "movesWithModel": False,
        "onePlatePerComponent": True,
        "deduplicateOnlyWhenRenderedHashesMatch": True,
    }
    assert composition["model"]["format"] == "PNG-RGBA"
    assert composition["model"]["transparent"] is True
    assert composition["model"]["bakedUiElements"] == []
    assert composition["htmlOwnedElements"] == ["copy", "rail", "contentWash"]
    assert composition["contactShadow"]["included"] is False
    assert composition["contactShadow"]["inventWhenFloating"] is False
    assert composition["layout"]["traditionalTwoColumnCard"] is False
    assert motion == {
        "preset": "B",
        "translateXPx": 240,
        "uniformScale": 0.97,
        "durationMs": 820,
        "easing": "cubic-bezier(0.22, 1, 0.36, 1)",
        "implementedBy": "HTML-CSS-WAAPI",
        "bakedIntoModelPixels": False,
        "reverseUsesSameTimeline": True,
    }


def test_contract_covers_exact_three_states_and_same_assets_for_both_viewports():
    contract = _contract()
    states = contract["components"]

    assert set(states) == {"dual_channel_condenser_lens_assembly", "dual_channel_collection_optics_chamber"}
    assert set(states["dual_channel_condenser_lens_assembly"]["states"]) == {"mechanicalExpanded"}
    assert set(states["dual_channel_collection_optics_chamber"]["states"]) == {
        "mechanicalExpanded",
        "inspectionStable",
    }
    assert states["dual_channel_collection_optics_chamber"]["states"]["inspectionStable"]["completeExplanationCarrier"] is True
    assert states["dual_channel_collection_optics_chamber"]["states"]["mechanicalExpanded"]["completeExplanationCarrier"] is False
    assert states["dual_channel_condenser_lens_assembly"]["states"]["mechanicalExpanded"]["completeExplanationCarrier"] is True
    assert contract["viewportValidation"] == {
        "assetFactSource": "shared",
        "viewports": [[1280, 800], [900, 700]],
        "exactElementRectRequired": True,
        "viewportScalingToPassForbidden": True,
        "validateCompositionAndCropSeparately": True,
        "viewportLocked": False,
    }


def test_contract_requires_overscan_without_changing_real_viewports():
    contract = _contract()
    carrier = contract["render"]["transparentCarrier"]
    acceptance = contract["acceptance"]

    assert carrier["canvas"] == [2304, 1620]
    assert carrier["approvedReferenceWindow"] == {"x": 512, "y": 360, "width": 1280, "height": 900}
    assert carrier["overscanMargins"] == {"left": 512, "top": 360, "right": 512, "bottom": 360}
    assert carrier["projectionScale"] == {
        "resolution": 1.8,
        "lens": 0.5555555556,
        "shiftX": 0.5555555556,
        "shiftY": 0.5555555556,
        "cameraPoseUnchanged": True,
    }
    assert acceptance["alpha"]["borderAlphaMax"] == 0
    assert acceptance["sourceCanvasEdgeVisibleAtStart"] is False
    assert acceptance["sourceCanvasEdgeVisibleAtTerminalB"] is False
    assert acceptance["realViewportExpansionAllowed"] is False
    assert acceptance["contactShadowDecision"] == "show-real-sample-and-request-human-decision"


def test_overscan_keeps_source_canvas_edges_safely_outside_both_terminal_viewports():
    contract = _contract()
    carrier = contract["render"]["transparentCarrier"]
    reference = carrier["approvedReferenceWindow"]
    motion = contract["motion"]

    for viewport_width, viewport_height in contract["viewportValidation"]["viewports"]:
        fit = min(viewport_width / reference["width"], viewport_height / reference["height"])
        reference_left = (viewport_width - reference["width"] * fit) / 2
        canvas_left = reference_left - reference["x"] * fit
        origin_x = viewport_width / 2
        terminal_canvas_left = (
            origin_x
            + (canvas_left - origin_x) * motion["uniformScale"]
            + motion["translateXPx"]
        )
        assert terminal_canvas_left <= -64, (
            viewport_width,
            viewport_height,
            terminal_canvas_left,
        )


def test_contract_defines_closed_sample_outputs_and_recoverable_rollback():
    contract = _contract()
    closure = contract["outputClosure"]
    rollback = contract["rollback"]

    assert closure["contractPhaseFiles"] == [
        "work/two-component-asset-contract.json",
        "evidence/approved-complete-explanation-reference.png",
    ]
    assert len(closure["futureRenderedCoreFiles"]) == 5
    assert closure["unexpectedFilesAllowed"] is False
    assert contract["samplePlan"][0]["name"] == "low-resolution-overscan-preflight"
    assert contract["samplePlan"][1]["name"] == "full-quality-three-state-sample"
    assert rollback["sourceBlendSaved"] is False
    assert rollback["formalPathsWritten"] == []
    assert rollback["recovery"] == "remove only this isolated candidate root after explicit authorization"
    assert "TBD" not in json.dumps(contract)
    assert "TODO" not in json.dumps(contract)
