import importlib.util
import inspect
import json
import shutil
import sys
from pathlib import Path

import pytest
from PIL import Image

from tests.twinkle_stage4_fixtures import (
    build_pending_c2,
    make_browser_evidence,
    make_stage4_core_evidence,
)


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "build_twinkle_stage4_orbit.py"
REJECTED_ORIENTATION_PROBE = (
    ROOT
    / "output"
    / ".twinkle-stage4-orientation-probe-20260828"
    / "orientation-probe-r1"
)
CORRECTION_FINAL_OUTPUT = (
    ROOT
    / "output"
    / ".twinkle-stage4-orientation-correction-20260828"
    / "orientation-correction-r1"
)
ORBIT_O1_OUTPUT = (
    ROOT
    / "output"
    / ".twinkle-stage4-orbit-o1-20260829"
    / "orbit-o1"
)
SURFACE_ANCHOR_PRECHECK_OUTPUT = (
    ROOT
    / "output"
    / ".twinkle-stage4-surface-anchor-precheck-20260829"
    / "surface-anchor-precheck-r1"
)
C360_F96_OUTPUT = (
    ROOT
    / "output"
    / ".twinkle-stage4-orbit-c360-f96-20260829"
    / "orbit-c360-f96-r1"
)
C1_KEYFRAME_OUTPUT = (
    ROOT
    / "output"
    / ".twinkle-stage4-c1-keyframe-precheck-20260830"
    / "c1-keyframe-precheck-r1"
)
C2_FULL_REVIEW_OUTPUT = (
    ROOT
    / "output"
    / ".twinkle-stage4-c2-full-review-20260830"
    / "c2-full-review-r1"
)
CHAMBER = "dual_channel_collection_optics_chamber"
CONDENSER = "dual_channel_condenser_lens_assembly"
C2_ROUTE_IDS = [
    f"{unit}--entry-{entry:03d}--{variant}"
    for unit, entries in ((CHAMBER, (6, 65)), (CONDENSER, (87, 8)))
    for entry in entries
    for variant in ("A", "B")
]


assert MODULE_PATH.is_file(), "stage 4 orbit contract module is missing"
spec = importlib.util.spec_from_file_location("build_twinkle_stage4_orbit", MODULE_PATH)
stage4 = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(stage4)


HISTORICAL_OUTPUT_TESTS = {
    "test_correction_recovery_accepts_only_the_recorded_first_frame",
    "test_rejected_track_to_chamber_focus_is_detected_as_black_empty_and_different",
    "test_correction_render_profile_is_exactly_the_stage1_approved_contract",
    "test_stage1_focus_projection_keeps_target_and_subject_in_frame",
    "test_correction_validator_requires_visual_profile_orientation_and_restoration",
    "test_orientation_correction_builder_uses_three_new_frames_and_labels_failures",
    "test_correction_main_review_cells_reference_only_three_candidates",
    "test_current_correction_manifest_uses_only_refreshed_candidate_sources",
    "test_review_refresh_is_idempotent_and_never_changes_candidate_frames",
    "test_track_to_six_grid_cells_cover_both_units_start_mid_end",
    "test_six_grid_review_refresh_adds_only_review_artifact",
    "test_human_approval_is_bound_to_track_to_six_grid_and_does_not_authorize_step5",
    "test_o1_candidate_has_exact_frames_qualification_review_and_pending_human_gate",
    "test_surface_anchor_precheck_assets_are_exact_and_preserve_narrow_human_gate",
    "test_surface_anchor_recovery_reuses_the_completed_zero_render_worker",
    "test_surface_approval_selects_only_two_locations_and_authorizes_nothing_else",
    "test_c360_component_recognizability_uses_complete_overview_projection",
    "test_c360_review_refresh_changes_only_zero_render_derived_audit_files",
    "test_c360_human_review_approval_is_bound_to_reviewed_scope_only",
    "test_c360_f96_candidate_has_dynamic_review_and_approved_human_gate",
    "test_c360_auxiliary_contact_sheet_uses_readable_three_line_cells",
}


@pytest.fixture(scope="module", autouse=True)
def stage4_core_evidence(tmp_path_factory):
    patcher = pytest.MonkeyPatch()
    evidence = make_stage4_core_evidence(
        stage4, tmp_path_factory.mktemp("twinkle-stage4-core"), patcher
    )
    patcher.setattr(stage4, "APPROVED_C360_F96", evidence.c360)
    patcher.setattr(stage4, "C1_KEYFRAME_OUTPUT_ROOT", evidence.c1)
    module = sys.modules[__name__]
    patcher.setattr(module, "C360_F96_OUTPUT", evidence.c360)
    patcher.setattr(module, "C1_KEYFRAME_OUTPUT", evidence.c1)
    patcher.setattr(module, "C2_FULL_REVIEW_OUTPUT", evidence.c2)
    yield evidence
    patcher.undo()


@pytest.fixture(autouse=True)
def mark_unmaterialized_history_as_non_core(request):
    if getattr(request.node, "originalname", request.node.name) in HISTORICAL_OUTPUT_TESTS:
        pytest.skip(
            "non-core historical visual evidence is intentionally not materialized "
            "in clean-checkout regression"
        )


def require_step8_integration_assets(*, include_c2=False):
    required = [C1_KEYFRAME_OUTPUT, C360_F96_OUTPUT, stage4.STAGE3_R2_MANIFEST]
    if include_c2:
        required.append(C2_FULL_REVIEW_OUTPUT)
    missing = [str(path) for path in required if not Path(path).exists()]
    if missing:
        raise AssertionError(
            "core C2/step9 fixture inputs are missing: " + ", ".join(missing)
        )


def copy_c2_pending_browser_candidate(destination):
    require_step8_integration_assets(include_c2=True)
    shutil.copytree(C2_FULL_REVIEW_OUTPUT, destination)
    browser_root = destination / "browser-results"
    if browser_root.exists():
        shutil.rmtree(browser_root)
    manifest_path = destination / "c2-full-review-manifest.json"
    report = json.loads(manifest_path.read_text(encoding="utf-8"))
    report["humanVisualApproved"] = False
    report["authorizesStep9"] = False
    report["stage4Closed"] = False
    report.pop("focusRouteGenerated", None)
    report.pop("routeByUnit", None)
    report.pop("entryFrameSet", None)
    report.pop("stage4Closure", None)
    report["browserMachinePassed"] = False
    report["browserEvidence"] = []
    report["machinePassed"] = False
    report["inventorySha256"] = {
        path.relative_to(destination).as_posix(): stage4.sha256(path)
        for path in sorted(destination.rglob("*"))
        if path.is_file() and path != manifest_path
    }
    manifest_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return destination


def copy_c2_pending_step9_candidate(destination):
    require_step8_integration_assets(include_c2=True)
    shutil.copytree(C2_FULL_REVIEW_OUTPUT, destination)
    manifest_path = destination / "c2-full-review-manifest.json"
    report = json.loads(manifest_path.read_text(encoding="utf-8"))
    report["humanVisualApproved"] = False
    report["authorizesStep9"] = False
    report["stage4Closed"] = False
    report.pop("focusRouteGenerated", None)
    report.pop("routeByUnit", None)
    report.pop("entryFrameSet", None)
    report.pop("stage4Closure", None)
    manifest_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return destination


def make_c2_browser_evidence(report):
    binding = {
        "reviewAssetInventorySha256": report["reviewAssetInventorySha256"],
        "reviewPageSha256": report["reviewPageSha256"],
    }
    success = {
        "passed": True,
        "imagesLoaded": True,
        "pauseHeld": True,
        "resumeSameDirection": True,
        "resumeFromHeldPoint": True,
        "modelEntryCovered": True,
        "nameEntryCovered": True,
        "routeCoverage": C2_ROUTE_IDS,
        "routeSwitchDuringFocusSafe": True,
        "replayDuringFocusSafe": True,
        "fallbackDuringFocusSafe": True,
        "routeSwitchDuringInspectionSafe": True,
        "replayDuringInspectionSafe": True,
        "fallbackDuringInspectionSafe": True,
        "boundedWaitFailureObserved": True,
        "timedOut": False,
        "captureFrameRestored": True,
        "staticFallbackShown": True,
        "failurePathEntered": False,
        "requestFailures": [],
        "consoleErrors": [],
        "consoleWarnings": [],
        **binding,
    }
    return [
        {"scenario": "desktop", "browserId": "chromium", "viewport": [1440, 1000], **success},
        {"scenario": "mobile", "browserId": "chromium", "viewport": [390, 844], **success},
        {
            "scenario": "injected-failure",
            "browserId": "chromium",
            "viewport": [1440, 1000],
            "passed": True,
            "imagesLoaded": False,
            "failurePathEntered": True,
            "requestFailures": ["/__c2_injected_missing_asset__.png"],
            "consoleErrors": ["expected injected missing asset 404"],
            "consoleWarnings": [],
            **binding,
        },
        {
            "scenario": "bounded-timeout",
            "browserId": "chromium",
            "viewport": [1440, 1000],
            "passed": False,
            "timedOut": True,
            "timeoutPhase": "harness-timeout-probe",
            "durationMs": 20,
            "requestFailures": [],
            "consoleErrors": [],
            "consoleWarnings": [],
            **binding,
        },
    ]


def approved_step9_choices():
    return {
        CHAMBER: {6: "A", 65: "B"},
        CONDENSER: {87: "A", 8: "A"},
    }


def test_approved_pingpong_profile_uses_the_exact_expanded_sequence():
    assert stage4.ORBIT_PROFILE == {
        "topology": "pingpong-expanded",
        "azimuthDegreesRelativeToV7": [-12.0, 12.0],
        "elevationMode": "fixed",
        "durationMs": 10_000,
        "physicalFrameCount": 49,
        "logicalIndexCount": 96,
        "maximumEntryFramesPerUnit": 2,
    }
    assert stage4.expanded_physical_frames() == tuple(
        list(range(49)) + list(range(47, 0, -1))
    )


@pytest.mark.parametrize(
    ("current_index", "entries", "direction", "expected"),
    [
        (10, (4, 18), "forward", 4),
        (10, (4, 16), "forward", 16),
        (10, (4, 16), "backward", 4),
        (50, (48, 90), "backward", 48),
    ],
)
def test_nearest_entry_uses_absolute_expanded_index_distance_and_direction_ties(
    current_index, entries, direction, expected
):
    assert (
        stage4.select_nearest_entry(current_index, entries, direction) == expected
    )


@pytest.mark.parametrize("playback", ["running", "paused"])
def test_both_name_buttons_are_enabled_on_every_global_frame(playback):
    controls = stage4.global_controls(
        orbit_frame_index=95,
        orbit_playback=playback,
        qualification_by_unit={CHAMBER: False, CONDENSER: False},
    )
    assert controls["unitNames"] == {
        CHAMBER: {"visible": True, "enabled": True},
        CONDENSER: {"visible": True, "enabled": True},
    }


@pytest.mark.parametrize(
    ("overrides", "eligible"),
    [
        ({}, True),
        ({"depthPositive": False}, False),
        ({"projectionSafe": False}, False),
        ({"facingCamera": False}, False),
        ({"unoccluded": False}, False),
        ({"humanApproved": False}, False),
    ],
)
def test_model_hotspot_visibility_and_enablement_follow_frame_qualification(
    overrides, eligible
):
    record = {
        "depthPositive": True,
        "projectionSafe": True,
        "facingCamera": True,
        "unoccluded": True,
        "humanApproved": True,
    }
    record.update(overrides)
    assert stage4.model_hotspot_control(record) == {
        "visible": eligible,
        "enabled": eligible,
    }


def test_authority_is_exactly_stage1_and_closed_stage3_r2(stage4_core_evidence):
    authority = stage4.validate_authority()
    assert stage4.SEMANTIC_UNITS == (CHAMBER, CONDENSER)
    assert stage4.STAGE1_MANIFEST == stage4_core_evidence.stage1_manifest
    assert stage4.STAGE3_R2_MANIFEST == stage4_core_evidence.stage3_manifest
    assert stage4.sha256(stage4.STAGE1_MANIFEST) == stage4.EXPECTED_STAGE1_SHA256
    assert stage4.sha256(stage4.STAGE3_R2_MANIFEST) == (
        stage4.EXPECTED_STAGE3_R2_SHA256
    )
    assert authority["stage3"]["machinePassed"] is True
    assert authority["stage3"]["humanVisualApproved"] is True
    assert authority["stage3"]["stage3Closed"] is True
    assert authority["stage3"]["authorizesStage4"] is False


@pytest.mark.parametrize(
    ("changes", "error"),
    [
        ({"stage1Manifest": "experiment-manifest.json"}, "stage 1 authority"),
        ({"stage3Manifest": "old-motion-manifest.json"}, "stage 3 r2 authority"),
        ({"semanticUnits": ["j_green_filter_subassembly", CONDENSER]}, "semantic"),
        ({"payloadTerms": ["f_dual_acl_housing"]}, "legacy"),
        ({"payloadTerms": ["green-filter", "red-filter"]}, "filter"),
        ({"writeProductionPage": True}, "production page"),
    ],
)
def test_request_validation_rejects_retired_or_unauthorized_contracts(
    tmp_path, changes, error
):
    request = stage4.default_request(tmp_path / "new-output")
    request.update(changes)
    with pytest.raises(ValueError, match=error):
        stage4.validate_request(request)


def test_request_validation_refuses_output_overwrite(tmp_path):
    output_root = tmp_path / "existing"
    output_root.mkdir()
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        stage4.validate_request(stage4.default_request(output_root))


def test_step3_remains_pure_and_does_not_create_a_second_timeline_or_engines():
    source = Path(stage4.__file__).read_text(encoding="utf-8")
    assert "import bpy" not in source
    assert "networkx" not in source
    assert "scipy" not in source
    assert "world_to_camera_view" not in source
    assert "def project_" not in source
    assert stage4.TIMELINE_OWNER == "stage3-state-machine"


def test_orientation_probe_is_bounded_to_native_constraints_and_semantic_poses():
    assert stage4.ORIENTATION_PROBE == {
        "constraints": ("TRACK_TO", "LOCKED_TRACK"),
        "units": (CHAMBER, CONDENSER),
        "semanticPoses": ("entry", "transition", "focus"),
        "render": {"resolution": [640, 450], "samples": 64},
        "renderFrameCount": 12,
        "maximumRenderFrameCount": 15,
        "curveKind": "CURVE",
        "pathConstraint": "FOLLOW_PATH",
        "fCurveDriven": True,
        "candidateBlendSaved": False,
    }


def test_orientation_probe_blender_command_is_background_and_fail_closed(tmp_path):
    output_root = tmp_path.resolve()
    command = stage4.orientation_probe_blender_command(
        "blender.exe", "candidate.blend", output_root
    )
    assert command[:3] == ["blender.exe", "--background", "candidate.blend"]
    python_index = command.index("--python")
    assert command[python_index - 2 : python_index] == ["--python-exit-code", "1"]
    assert Path(command[python_index + 1]).resolve() == MODULE_PATH.resolve()
    assert command[-2:] == ["--stage4-orientation-worker", str(output_root)]


def test_common_orientation_selection_uses_machine_evidence_not_preference():
    results = {
        "TRACK_TO": {
            "passesCommonGate": True,
            "maximumRollDegrees": 0.04,
            "maximumEndpointRotationErrorDegrees": 0.03,
        },
        "LOCKED_TRACK": {
            "passesCommonGate": False,
            "maximumRollDegrees": 11.0,
            "maximumEndpointRotationErrorDegrees": 9.0,
        },
    }
    assert stage4.choose_common_orientation(results) == "TRACK_TO"


def test_orientation_probe_validator_requires_restoration_and_exact_inventory(tmp_path):
    output_root = tmp_path / "orientation-probe-r1"
    frames = output_root / "frames"
    frames.mkdir(parents=True)
    for index in range(12):
        (frames / f"pose-{index:02d}.png").write_bytes(f"pose-{index}".encode())
    (output_root / "technical-pose-contact-sheet.png").write_bytes(b"sheet")
    (output_root / "worker-audit.json").write_text("{}", encoding="utf-8")
    report = {
        "schema": "twinkle-stage4-orientation-probe-v1",
        "contract": stage4.orientation_probe_record(),
        "selectedConstraint": "TRACK_TO",
        "constraintResults": {
            "TRACK_TO": {"passesCommonGate": True},
            "LOCKED_TRACK": {"passesCommonGate": False},
        },
        "renderFrameCount": 12,
        "machinePassed": True,
        "humanApproved": False,
        "authorizesStep5": False,
        "restoration": {
            "candidateBlendSha256Before": stage4.EXPECTED_CANDIDATE_BLEND_SHA256,
            "candidateBlendSha256After": stage4.EXPECTED_CANDIDATE_BLEND_SHA256,
            "candidateBlendSaved": False,
            "cameraTransformRestored": True,
            "sceneSettingsRestored": True,
            "temporaryCurvesRemaining": [],
            "temporaryEmptiesRemaining": [],
            "temporaryConstraintsRemaining": [],
            "temporaryActionsRemaining": [],
        },
    }
    inventory = {
        path.relative_to(output_root).as_posix(): stage4.sha256(path)
        for path in sorted(output_root.rglob("*"))
        if path.is_file()
    }
    report["inventorySha256"] = inventory
    (output_root / "orientation-probe-manifest.json").write_text(
        json.dumps(report), encoding="utf-8"
    )
    assert stage4.validate_orientation_probe(output_root)["machinePassed"] is True

    report["restoration"]["temporaryActionsRemaining"] = ["TEMP__STAGE4_ACTION"]
    (output_root / "orientation-probe-manifest.json").write_text(
        json.dumps(report), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="restoration"):
        stage4.validate_orientation_probe(output_root)


def test_orientation_probe_builder_assembles_isolated_machine_evidence(tmp_path):
    output_root = tmp_path / "orientation-probe-r1"

    def fake_runner(command, *, cwd):
        staging = Path(command[-1])
        frames = staging / "frames"
        frames.mkdir(parents=True)
        records = []
        index = 0
        for method in stage4.ORIENTATION_PROBE["constraints"]:
            for unit in stage4.SEMANTIC_UNITS:
                for pose in stage4.ORIENTATION_PROBE["semanticPoses"]:
                    relative = f"frames/pose-{index:02d}.png"
                    Image.new("RGB", (64, 45), (20 + index, 30, 40)).save(
                        staging / relative
                    )
                    records.append(
                        {
                            "index": index,
                            "constraint": method,
                            "unit": unit,
                            "pose": pose,
                            "path": relative,
                        }
                    )
                    index += 1
        audit = {
            "schema": "twinkle-stage4-orientation-worker-v1",
            "renderFrameCount": 12,
            "frames": records,
            "constraintResults": {
                "TRACK_TO": {
                    "passesCommonGate": True,
                    "maximumRollDegrees": 0.0,
                    "maximumEndpointRotationErrorDegrees": 0.0,
                },
                "LOCKED_TRACK": {
                    "passesCommonGate": False,
                    "maximumRollDegrees": 8.0,
                    "maximumEndpointRotationErrorDegrees": 7.0,
                },
            },
            "restoration": {
                "candidateBlendSha256Before": stage4.EXPECTED_CANDIDATE_BLEND_SHA256,
                "candidateBlendSha256After": stage4.EXPECTED_CANDIDATE_BLEND_SHA256,
                "candidateBlendSaved": False,
                "cameraTransformRestored": True,
                "sceneSettingsRestored": True,
                "temporaryCurvesRemaining": [],
                "temporaryEmptiesRemaining": [],
                "temporaryConstraintsRemaining": [],
                "temporaryActionsRemaining": [],
            },
        }
        (staging / "worker-audit.json").write_text(
            json.dumps(audit), encoding="utf-8"
        )

    report = stage4.build_orientation_probe(
        output_root, blender="blender.exe", runner=fake_runner
    )
    assert report["selectedConstraint"] == "TRACK_TO"
    assert report["renderFrameCount"] == 12
    assert (output_root / "technical-pose-contact-sheet.png").is_file()
    assert not list(output_root.rglob("*.blend"))

    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        stage4.build_orientation_probe(
            output_root, blender="blender.exe", runner=fake_runner
        )


def test_orientation_worker_uses_only_blender_native_path_orientation_primitives():
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert callable(stage4.orientation_probe_worker)
    assert ".curves.new(" in source
    assert 'constraints.new(type="FOLLOW_PATH")' in source
    assert 'constraints.new(type=method)' in source
    assert "fcurves.new(" in source
    assert ".keyframe_points.add(" in source
    assert "TRACK_TO" in source and "LOCKED_TRACK" in source
    assert "save_as_mainfile" not in source
    assert "save_mainfile" not in source


def test_orientation_worker_staging_must_exist_and_be_empty(tmp_path):
    empty = tmp_path / "empty-staging"
    empty.mkdir()
    assert stage4.validate_orientation_worker_staging(empty) == empty.resolve()

    nonempty = tmp_path / "nonempty-staging"
    nonempty.mkdir()
    (nonempty / "unexpected.txt").write_text("occupied", encoding="utf-8")
    with pytest.raises(ValueError, match="must be empty"):
        stage4.validate_orientation_worker_staging(nonempty)

    with pytest.raises(ValueError, match="must already exist"):
        stage4.validate_orientation_worker_staging(tmp_path / "missing")


def test_public_orientation_correction_is_track_to_only_and_uses_three_renders():
    assert stage4.ORIENTATION_CORRECTION == {
        "constraint": "TRACK_TO",
        "render": {"resolution": [640, 450], "samples": 64},
        "renders": (
            {"unit": CHAMBER, "pose": "focus", "sourceFrame": 101},
            {"unit": CONDENSER, "pose": "transition", "sourceFrame": 51},
            {"unit": CONDENSER, "pose": "focus", "sourceFrame": 101},
        ),
        "renderFrameCount": 3,
        "maximumRenderFrameCount": 3,
        "reusesRejectedLockedTrackEvidence": True,
        "testsConstraintCombination": False,
        "candidateBlendSaved": False,
    }


@pytest.mark.parametrize("unit", [CHAMBER, CONDENSER])
def test_correction_camera_intrinsics_are_exactly_stage1_approved(unit):
    authority = stage4.validate_authority()["stage1"]
    assert stage4.correction_camera_intrinsics(unit) == {
        "lensMm": authority["units"][unit]["camera"]["lensMm"],
        "sensorWidthMm": authority["units"][unit]["camera"]["sensorWidthMm"],
        "shiftX": authority["units"][unit]["camera"]["shiftX"],
        "shiftY": authority["units"][unit]["camera"]["shiftY"],
    }


def test_rejected_track_to_chamber_focus_is_detected_as_black_empty_and_different():
    authority = stage4.validate_authority()["stage1"]
    unit = authority["units"][CHAMBER]
    metrics = stage4.compare_endpoint_frame(
        REJECTED_ORIENTATION_PROBE / "frames" / "pose-02.png",
        stage4.STAGE1_MANIFEST.parent / unit["frames"]["focused-settled"]["asset"],
    )
    assert metrics["blackFrame"] is True
    assert metrics["emptyFrame"] is True
    assert metrics["nearBlackFraction"] > 0.95
    assert metrics["referenceRgbMae"] > 100.0


def test_correction_render_profile_is_exactly_the_stage1_approved_contract():
    authority = stage4.validate_authority()["stage1"]
    profile = authority["renderProfile"]
    assert stage4.correction_render_profile() == {
        "engine": profile["engine"],
        "filmTransparent": profile["filmTransparent"],
        "colorManagement": profile["colorManagement"],
        "sharedHiddenObjects": profile["sharedHiddenObjects"],
        "sharedTechnicalLights": profile["sharedTechnicalLights"],
        "lightRigHash": profile["lightRigHash"],
        "materialRule": profile["materialRule"],
        "materialRuleHash": profile["materialRuleHash"],
        "colorManagementHash": profile["colorManagementHash"],
    }


def test_correction_worker_applies_native_track_to_profile_and_restoration():
    source = inspect.getsource(stage4.orientation_correction_worker)
    assert 'constraints.new(type="FOLLOW_PATH")' in source
    assert 'constraints.new(type="TRACK_TO")' in source
    assert "LOCKED_TRACK" not in source
    for token in (
        "lensMm",
        "sensorWidthMm",
        "shiftX",
        "shiftY",
        "sharedHiddenObjects",
        "sharedTechnicalLights",
        "colorManagement",
        "materialRule",
        "temporaryLightsRemaining",
        "temporaryMaterialsRemaining",
    ):
        assert token in source
    assert "save_as_mainfile" not in source
    assert "save_mainfile" not in source


def test_rejected_probe_is_not_valid_correction_evidence():
    with pytest.raises(ValueError, match="correction schema"):
        stage4.validate_orientation_correction(REJECTED_ORIENTATION_PROBE)


@pytest.mark.parametrize("unit", [CHAMBER, CONDENSER])
def test_stage1_focus_projection_keeps_target_and_subject_in_frame(unit):
    authority = stage4.validate_authority()["stage1"]
    camera = authority["units"][unit]["camera"]
    record = stage4.correction_projection_record(
        unit,
        camera_location=camera["location"],
        camera_target=camera["target"],
    )
    assert record["targetClipped"] is False
    assert record["subjectOutOfFrame"] is False
    assert record["failureReasons"] == []
    assert record["visibleSubjectFraction"] >= 0.75
    assert record["visibleCanvasArea"] >= 0.005


def test_projection_module_loads_from_the_authoritative_absolute_path():
    module = stage4.load_camera_projection_module()
    assert Path(module.__file__).resolve() == (
        ROOT / "scripts" / "twinkle_camera_projection.py"
    ).resolve()
    assert callable(module.project_bounds)
    assert callable(module.project_world_point)


def test_named_datablock_cleanup_is_idempotent():
    class FakeCollection:
        def __init__(self):
            self.items = {"TEMP": object()}

        def get(self, name):
            return self.items.get(name)

        def remove(self, item, **kwargs):
            name = next(key for key, value in self.items.items() if value is item)
            del self.items[name]

    collection = FakeCollection()
    assert stage4.remove_named_datablock(collection, "TEMP") is True
    assert stage4.remove_named_datablock(collection, "TEMP") is False


def test_correction_recovery_accepts_only_the_recorded_first_frame(tmp_path):
    recovery_staging = tmp_path / ".orientation-correction-recovery"
    (recovery_staging / "frames").mkdir(parents=True)
    shutil.copyfile(
        CORRECTION_FINAL_OUTPUT / "frames" / "candidate-00.png",
        recovery_staging / "frames" / "candidate-00.png",
    )
    recovery = stage4.validate_orientation_correction_recovery_staging(
        recovery_staging
    )
    assert recovery == {
        "reusedFrameIndex": 0,
        "path": "frames/candidate-00.png",
        "sha256": "550677558E719C71E08BD1F968165F4FB161648BB8BD65E495A53BAB5C3DCCEB",
        "renderedFrameIndicesRemaining": [1, 2],
    }
    command = stage4.orientation_correction_blender_command(
        "blender.exe",
        "candidate.blend",
        recovery_staging.resolve(),
        resume_candidate_00=True,
    )
    assert "--resume-candidate-00" in command
    assert command[-2:] == [
        "--stage4-orientation-correction-worker",
        str(recovery_staging.resolve()),
    ]


def test_correction_validator_requires_visual_profile_orientation_and_restoration(tmp_path):
    output_root = tmp_path / "orientation-correction-r1"
    frames_root = output_root / "frames"
    frames_root.mkdir(parents=True)
    frame_records = []
    for index, render in enumerate(stage4.ORIENTATION_CORRECTION["renders"]):
        relative = f"frames/candidate-{index:02d}.png"
        (output_root / relative).write_bytes(f"candidate-{index}".encode())
        quality = {
            "blackFrame": False,
            "emptyFrame": False,
            "meanLuminance": 120.0,
            "nearBlackFraction": 0.05,
            "dynamicRange": 240,
        }
        if render["pose"] == "focus":
            quality.update(
                {
                    "referenceScale": "LANCZOS",
                    "referenceRgbMae": 5.0,
                    "referenceAsset": "approved-endpoint.png",
                }
            )
        frame_records.append(
            {
                "index": index,
                **render,
                "path": relative,
                "cameraIntrinsics": stage4.correction_camera_intrinsics(
                    render["unit"]
                ),
                "quality": quality,
                "projection": {
                    "method": "twinkle_camera_projection-authority-hull",
                    "geometrySnapshotSha256": stage4.EXPECTED_GEOMETRY_SNAPSHOT_SHA256,
                    "safeTargetBounds": [0.05, 0.05, 0.69, 0.95],
                    "minimumVisibleSubjectFraction": 0.75,
                    "minimumVisibleCanvasArea": 0.005,
                    "targetCenter": [0.5, 0.5],
                    "targetDepthPositive": True,
                    "subjectBounds": [0.2, 0.2, 0.6, 0.6],
                    "visibleSubjectFraction": 1.0,
                    "visibleCanvasArea": 0.16,
                    "targetClipped": False,
                    "subjectOutOfFrame": False,
                    "failureReasons": [],
                },
            }
        )
    (output_root / "technical-pose-contact-sheet.png").write_bytes(b"sheet")
    (output_root / "worker-audit.json").write_text("{}", encoding="utf-8")
    report = {
        "schema": "twinkle-stage4-orientation-correction-v1",
        "contract": stage4.orientation_correction_record(),
        "constraint": "TRACK_TO",
        "renderProfile": stage4.correction_render_profile(),
        "reviewSheetSources": [
            "frames/candidate-00.png",
            "frames/candidate-01.png",
            "frames/candidate-02.png",
        ],
        "reviewFont": stage4.correction_review_font(),
        "renderFrameCount": 3,
        "budgetEvidence": {
            "initialProbeRenders": 12,
            "correctionRendersBeforeRecovery": [0],
            "reusedFrameIndices": [0],
            "renderedFrameIndicesThisRun": [1, 2],
            "totalOrientationRenders": 15,
        },
        "frames": frame_records,
        "orientationMetrics": {
            "maximumTargetErrorDegrees": 0.0,
            "maximumRollDegrees": 0.0,
            "maximumEndpointRotationErrorDegrees": 0.0,
            "maximumEndpointLocationErrorM": 0.0,
            "minimumUpDotWorldZ": 0.7,
            "maximumOrientationStepDegrees": 8.0,
            "flipCount": 0,
            "constraintCompetition": False,
            "evaluationLoopDetected": False,
        },
        "restoration": {
            "candidateBlendSha256Before": stage4.EXPECTED_CANDIDATE_BLEND_SHA256,
            "candidateBlendSha256After": stage4.EXPECTED_CANDIDATE_BLEND_SHA256,
            "candidateBlendSaved": False,
            "sourceCameraTransformRestored": True,
            "sceneSettingsRestored": True,
            "visibilityRestored": True,
            "materialRestored": True,
            "temporaryCamerasRemaining": [],
            "temporaryCurvesRemaining": [],
            "temporaryEmptiesRemaining": [],
            "temporaryLightsRemaining": [],
            "temporaryMaterialsRemaining": [],
            "temporaryConstraintsRemaining": [],
            "temporaryActionsRemaining": [],
        },
        "machinePassed": True,
        "humanApproved": False,
        "authorizesStep5": False,
    }
    inventory = {
        path.relative_to(output_root).as_posix(): stage4.sha256(path)
        for path in sorted(output_root.rglob("*"))
        if path.is_file()
    }
    report["inventorySha256"] = inventory
    manifest = output_root / "orientation-correction-manifest.json"
    manifest.write_text(json.dumps(report), encoding="utf-8")
    assert stage4.validate_orientation_correction(output_root)["machinePassed"] is True

    report["frames"][0]["quality"]["blackFrame"] = True
    manifest.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ValueError, match="black or empty"):
        stage4.validate_orientation_correction(output_root)

    report["frames"][0]["quality"]["blackFrame"] = False
    report["restoration"]["temporaryLightsRemaining"] = ["TEMP__STAGE4_LIGHT"]
    manifest.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ValueError, match="restoration"):
        stage4.validate_orientation_correction(output_root)

    report["restoration"]["temporaryLightsRemaining"] = []
    report["frames"][0]["projection"].update(
        {
            "subjectBounds": [-1.5, -1.0, 0.1, 0.1],
            "visibleSubjectFraction": 0.005681818181818183,
            "visibleCanvasArea": 0.01,
            "subjectOutOfFrame": True,
            "failureReasons": ["subject-out-of-frame"],
        }
    )
    manifest.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ValueError, match="subject-out-of-frame"):
        stage4.validate_orientation_correction(output_root)

    report["frames"][0]["projection"].update(
        {
            "targetCenter": [0.9, 0.5],
            "targetClipped": True,
            "subjectBounds": [0.2, 0.2, 0.6, 0.6],
            "visibleSubjectFraction": 1.0,
            "visibleCanvasArea": 0.16,
            "subjectOutOfFrame": False,
            "failureReasons": ["target-clipped"],
        }
    )
    manifest.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ValueError, match="target-clipped"):
        stage4.validate_orientation_correction(output_root)


def test_orientation_correction_builder_uses_three_new_frames_and_labels_failures(tmp_path):
    output_root = tmp_path / "orientation-correction-r1"

    def fake_runner(command, *, cwd):
        staging = Path(command[-1])
        frames_root = staging / "frames"
        frames_root.mkdir()
        authority = stage4.validate_authority()["stage1"]
        records = []
        for index, render in enumerate(stage4.ORIENTATION_CORRECTION["renders"]):
            unit = authority["units"][render["unit"]]
            source = (
                stage4.STAGE1_MANIFEST.parent
                / unit["frames"]["focused-settled"]["asset"]
            )
            with Image.open(source) as approved:
                approved.convert("RGB").resize(
                    (640, 450), Image.Resampling.LANCZOS
                ).save(frames_root / f"candidate-{index:02d}.png")
            camera = unit["camera"]
            records.append(
                {
                    "index": index,
                    **render,
                    "path": f"frames/candidate-{index:02d}.png",
                    "cameraIntrinsics": stage4.correction_camera_intrinsics(
                        render["unit"]
                    ),
                    "projection": stage4.correction_projection_record(
                        render["unit"],
                        camera_location=camera["location"],
                        camera_target=camera["target"],
                    ),
                }
            )
        audit = {
            "schema": "twinkle-stage4-orientation-correction-worker-v1",
            "constraint": "TRACK_TO",
            "renderProfile": stage4.correction_render_profile(),
            "renderFrameCount": 3,
            "budgetEvidence": {
                "initialProbeRenders": 12,
                "correctionRendersBeforeRecovery": [0],
                "reusedFrameIndices": [0],
                "renderedFrameIndicesThisRun": [1, 2],
                "totalOrientationRenders": 15,
            },
            "frames": records,
            "orientationMetrics": {
                "maximumTargetErrorDegrees": 0.0,
                "maximumRollDegrees": 0.0,
                "maximumEndpointRotationErrorDegrees": 0.0,
                "maximumEndpointLocationErrorM": 0.0,
                "minimumUpDotWorldZ": 0.7,
                "maximumOrientationStepDegrees": 8.0,
                "flipCount": 0,
                "constraintCompetition": False,
                "evaluationLoopDetected": False,
            },
            "restoration": {
                "candidateBlendSha256Before": stage4.EXPECTED_CANDIDATE_BLEND_SHA256,
                "candidateBlendSha256After": stage4.EXPECTED_CANDIDATE_BLEND_SHA256,
                "candidateBlendSaved": False,
                "sourceCameraTransformRestored": True,
                "sceneSettingsRestored": True,
                "visibilityRestored": True,
                "materialRestored": True,
                "temporaryCamerasRemaining": [],
                "temporaryCurvesRemaining": [],
                "temporaryEmptiesRemaining": [],
                "temporaryLightsRemaining": [],
                "temporaryMaterialsRemaining": [],
                "temporaryConstraintsRemaining": [],
                "temporaryActionsRemaining": [],
            },
        }
        (staging / "worker-audit.json").write_text(
            json.dumps(audit), encoding="utf-8"
        )

    report = stage4.build_orientation_correction(
        output_root, blender="blender.exe", runner=fake_runner
    )
    assert report["constraint"] == "TRACK_TO"
    assert report["renderFrameCount"] == 3
    assert all(not frame["quality"]["blackFrame"] for frame in report["frames"])
    assert all(not frame["projection"]["failureReasons"] for frame in report["frames"])
    assert report["reviewLabels"] == {
        "candidate": "CANDIDATE / 候选",
        "failed": "FAILED / 失败",
    }
    assert (output_root / "technical-pose-contact-sheet.png").is_file()
    assert not list(output_root.rglob("*.blend"))

    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        stage4.build_orientation_correction(
            output_root, blender="blender.exe", runner=fake_runner
        )


def test_correction_main_review_cells_reference_only_three_candidates():
    cells = stage4.correction_review_cells(CORRECTION_FINAL_OUTPUT)
    assert [path.relative_to(CORRECTION_FINAL_OUTPUT).as_posix() for path, _ in cells] == [
        "frames/candidate-00.png",
        "frames/candidate-01.png",
        "frames/candidate-02.png",
    ]
    assert [label for _, label in cells] == [
        "候选｜双通道采集光学舱｜focus",
        "候选｜聚光镜组件｜transition",
        "候选｜聚光镜组件｜focus",
    ]
    assert all("FAILED" not in label and "失败" not in label for _, label in cells)


def test_correction_review_font_is_deterministic_and_supports_chinese():
    assert stage4.correction_review_font() == {
        "path": stage4.CORRECTION_REVIEW_FONT_PATH.as_posix(),
        "sha256": "D79C55E68B1131EEA0CC1C47BE4F572D964F28C682E143DB2AD09C1E4CB07A3F",
        "family": "Microsoft YaHei",
        "size": 18,
    }


def test_current_correction_manifest_uses_only_refreshed_candidate_sources():
    report = stage4.validate_orientation_correction(CORRECTION_FINAL_OUTPUT)
    assert report["reviewSheetSources"] == [
        "frames/candidate-00.png",
        "frames/candidate-01.png",
        "frames/candidate-02.png",
    ]


def test_review_refresh_is_idempotent_and_never_changes_candidate_frames(tmp_path):
    output_root = tmp_path / "orientation-correction-r1"
    shutil.copytree(CORRECTION_FINAL_OUTPUT, output_root)
    frame_hashes_before = {
        path.name: stage4.sha256(path)
        for path in sorted((output_root / "frames").glob("candidate-*.png"))
    }
    sheet_hash_before = stage4.sha256(
        output_root / "technical-pose-contact-sheet.png"
    )
    report = stage4.refresh_orientation_correction_review(output_root)
    frame_hashes_after = {
        path.name: stage4.sha256(path)
        for path in sorted((output_root / "frames").glob("candidate-*.png"))
    }
    assert frame_hashes_after == frame_hashes_before
    assert stage4.sha256(output_root / "technical-pose-contact-sheet.png") == sheet_hash_before
    assert report["reviewSheetSources"] == [
        "frames/candidate-00.png",
        "frames/candidate-01.png",
        "frames/candidate-02.png",
    ]
    assert report["reviewFont"] == stage4.correction_review_font()
    assert report["humanApproved"] is True
    assert report["authorizesStep5"] is False
    source = inspect.getsource(stage4.refresh_orientation_correction_review)
    assert "blender" not in source.lower()
    assert "subprocess" not in source.lower()


def test_track_to_six_grid_cells_cover_both_units_start_mid_end():
    cells = stage4.track_to_six_grid_cells(CORRECTION_FINAL_OUTPUT)
    assert [cell["label"] for cell in cells] == [
        "Track To｜双通道采集光学舱｜起点",
        "Track To｜双通道采集光学舱｜中途",
        "Track To｜双通道采集光学舱｜终点",
        "Track To｜聚光镜组件｜起点",
        "Track To｜聚光镜组件｜中途",
        "Track To｜聚光镜组件｜终点",
    ]
    assert [cell["source"] for cell in cells] == [
        "orientation-probe-r1/frames/pose-00.png",
        "orientation-probe-r1/frames/pose-01.png",
        "orientation-correction-r1/frames/candidate-00.png",
        "orientation-probe-r1/frames/pose-03.png",
        "orientation-correction-r1/frames/candidate-01.png",
        "orientation-correction-r1/frames/candidate-02.png",
    ]
    assert all(cell["constraint"] == "TRACK_TO" for cell in cells)
    assert all(cell["path"].is_file() for cell in cells)


def test_six_grid_review_refresh_adds_only_review_artifact(tmp_path):
    output_root = tmp_path / "orientation-correction-r1"
    shutil.copytree(CORRECTION_FINAL_OUTPUT, output_root)
    candidate_hashes_before = {
        path.name: stage4.sha256(path)
        for path in sorted((output_root / "frames").glob("candidate-*.png"))
    }
    report = stage4.refresh_track_to_six_grid_review(output_root)
    candidate_hashes_after = {
        path.name: stage4.sha256(path)
        for path in sorted((output_root / "frames").glob("candidate-*.png"))
    }
    assert candidate_hashes_after == candidate_hashes_before
    sheet = output_root / "track-to-six-grid-contact-sheet.png"
    assert sheet.is_file()
    with Image.open(sheet) as image:
        assert image.size == (960, 534)
    assert report["trackToSixGrid"]["sources"] == [
        "orientation-probe-r1/frames/pose-00.png",
        "orientation-probe-r1/frames/pose-01.png",
        "orientation-correction-r1/frames/candidate-00.png",
        "orientation-probe-r1/frames/pose-03.png",
        "orientation-correction-r1/frames/candidate-01.png",
        "orientation-correction-r1/frames/candidate-02.png",
    ]
    assert report["trackToSixGrid"]["font"] == stage4.correction_review_font()
    assert report["trackToSixGrid"]["sha256"] == stage4.sha256(sheet)
    assert report["humanApproved"] is True
    assert report["authorizesStep5"] is False


def test_human_approval_is_bound_to_track_to_six_grid_and_does_not_authorize_step5(
    tmp_path,
):
    output_root = tmp_path / "orientation-correction-r1"
    shutil.copytree(CORRECTION_FINAL_OUTPUT, output_root)
    manifest_path = output_root / "orientation-correction-manifest.json"
    pending = json.loads(manifest_path.read_text(encoding="utf-8"))
    pending["humanApproved"] = False
    pending.pop("humanApproval", None)
    pending["authorizesStep5"] = False
    manifest_path.write_text(json.dumps(pending), encoding="utf-8")
    report = stage4.record_orientation_correction_approval(
        output_root, approved_on="2026-08-29"
    )
    assert report["humanApproved"] is True
    assert report["humanApproval"] == {
        "approvedBy": "user",
        "approvedOn": "2026-08-29",
        "scope": "stage4-step4-track-to-common-orientation-and-six-grid-review-only",
        "approvedConstraint": "TRACK_TO",
        "approvedAsset": "track-to-six-grid-contact-sheet.png",
        "approvedAssetSha256": "FA1ABEF053FD20CF996B4EE5C6ECAFD57A00F24DE053052BD01D8ABDD2A039F0",
        "authorizesStep5": False,
    }
    assert report["authorizesStep5"] is False


def test_correction_worker_resume_reuses_zero_and_renders_only_one_and_two():
    source = inspect.getsource(stage4.orientation_correction_worker)
    assert "resume_candidate_00" in source
    assert "output_index == 0 and resume_candidate_00" in source
    assert '"renderedFrameIndicesThisRun": [1, 2]' in source
    assert '"reusedFrameIndices": [0]' in source


def test_o1_candidate_has_exact_frames_qualification_review_and_pending_human_gate():
    manifest_path = ORBIT_O1_OUTPUT / "orbit-o1-manifest.json"
    assert manifest_path.is_file(), "O1 candidate manifest is missing"
    report = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert report["schema"] == "twinkle-stage4-orbit-o1-v1"
    assert report["orbitProfile"] == stage4.ORBIT_PROFILE
    assert report["orientationConstraint"] == "TRACK_TO"
    assert report["render"] == {
        "resolution": [640, 450],
        "samples": 64,
        "format": "PNG",
        "lossless": True,
    }
    assert report["physicalFrameCount"] == 49
    assert report["logicalIndexCount"] == 96
    assert report["logicalPhysicalFrames"] == list(stage4.expanded_physical_frames())
    assert report["selectedSurfaceAnchorByUnit"] == {
        CHAMBER: "chamber-surface-02",
        CONDENSER: "condenser-surface-01",
    }
    assert report["surfaceAnchorManifestSha256"] == (
        "A27B447F6D235F748DCFB00A151D92E1D67408526544F831D298C2C598EA6105"
    )
    assert report["renderedFrameCount"] == 0
    assert report["reusedOrbitPngCount"] == 49
    assert report["totalStage4RenderedToDate"] == 64
    assert report["renderOperatorInvoked"] is False
    assert len(report["frames"]) == 49
    assert [frame["physicalFrameIndex"] for frame in report["frames"]] == list(
        range(49)
    )
    assert all(frame["quality"]["blackFrame"] is False for frame in report["frames"])
    assert all(frame["quality"]["emptyFrame"] is False for frame in report["frames"])
    assert all(frame["targetClipped"] is False for frame in report["frames"])
    assert all(frame["subjectOutOfFrame"] is False for frame in report["frames"])
    assert all(frame["camera"]["target"] for frame in report["frames"])
    assert all(frame["camera"]["up"] for frame in report["frames"])
    assert all("speedMetersPerSecond" in frame for frame in report["frames"])

    assert set(report["qualificationByUnit"]) == {CHAMBER, CONDENSER}
    for unit in (CHAMBER, CONDENSER):
        qualification = report["qualificationByUnit"][unit]
        assert len(qualification["physicalFrames"]) == 49
        assert len(qualification["logicalFrames"]) == 96
        assert qualification["machineQualifiedPhysicalFrames"]
        assert len(set(qualification["machineQualifiedPhysicalFrames"])) >= 2
        assert 1 <= len(qualification["initialEntryFrameSet"]) <= 2
        assert all(
            index in qualification["machineQualifiedLogicalFrames"]
            for index in qualification["initialEntryFrameSet"]
        )
        assert qualification["proposedHumanVisibleIntervals"]
        assert qualification["humanApproved"] is False

    required_review_assets = {
        "logical-index-map.json",
        "camera-path.json",
        "frame-qualification.json",
        "path-speed.png",
        "orbit-qualified-contact-sheet.png",
        "review/index.html",
        "worker-audit.json",
    }
    assert required_review_assets <= set(report["inventorySha256"])
    assert len(list((ORBIT_O1_OUTPUT / "frames").glob("frame-*.png"))) == 49
    assert report["machinePassed"] is True
    assert report["humanVisualApproved"] is False
    assert report["authorizesOrbitRepair"] is False
    assert report["authorizesStep6"] is False
    assert report["authorizesStage5"] is False
    assert report["budgetEvidence"] == {
        "orientationProbeRenders": 15,
        "orbitO1Renders": 49,
        "curveRenders": 0,
        "renderedThisRun": 0,
        "reusedOrbitPngCount": 49,
        "totalRenderedToDate": 64,
        "approvedFirstRoundBudget": 264,
        "remainingFirstRoundBudget": 200,
        "approvedMaximumBudget": 513,
    }
    assert report["restoration"]["candidateBlendSaved"] is False
    assert report["restoration"]["candidateBlendSha256Before"] == (
        stage4.EXPECTED_CANDIDATE_BLEND_SHA256
    )
    assert report["restoration"]["candidateBlendSha256After"] == (
        stage4.EXPECTED_CANDIDATE_BLEND_SHA256
    )
    assert all(
        not report["restoration"][field]
        for field in (
            "temporaryCamerasRemaining",
            "temporaryCurvesRemaining",
            "temporaryEmptiesRemaining",
            "temporaryLightsRemaining",
            "temporaryMaterialsRemaining",
            "temporaryConstraintsRemaining",
            "temporaryActionsRemaining",
        )
    )

    inventory = {
        path.relative_to(ORBIT_O1_OUTPUT).as_posix(): stage4.sha256(path)
        for path in sorted(ORBIT_O1_OUTPUT.rglob("*"))
        if path.is_file() and path != manifest_path
    }
    assert inventory == report["inventorySha256"]
    for index in range(49):
        final_frame = ORBIT_O1_OUTPUT / "frames" / f"frame-{index:03d}.png"
        source_frame = (
            ROOT
            / "output"
            / ".twinkle-stage4-orbit-o1-20260829"
            / ".orbit-o1-pdj85oh0"
            / "frames"
            / f"frame-{index:03d}.png"
        )
        assert stage4.sha256(final_frame) == stage4.sha256(source_frame)


def test_o1_blend_marker_mapping_is_confined_to_the_source_parsing_boundary():
    assert stage4.BLEND_MARKER_IDS == {
        CHAMBER: "j_green_filter_subassembly",
        CONDENSER: "f_dual_acl_housing",
    }
    source = inspect.getsource(stage4.orbit_o1_worker)
    assert 'HOTSPOT_ANCHOR__{marker_id}' in source
    assert 'FOCUS_TARGET__{marker_id}' in source
    assert 'distance=1.0' in source


def test_o1_final_builder_is_zero_render_and_uses_approved_surface_precheck():
    source = inspect.getsource(stage4.build_orbit_o1)
    assert "APPROVED_SURFACE_ANCHOR_PRECHECK" in source
    assert "FAILED_ORBIT_O1_ROOT" in source
    assert "orbit_o1_blender_command" not in source
    assert "bpy" not in source
    assert "runner(" not in source


def test_o1_review_html_treats_css_braces_as_literal_text(tmp_path):
    report = {
        "qualificationByUnit": {
            CHAMBER: {
                "proposedHumanVisibleIntervals": [[0, 95]],
                "initialEntryFrameSet": [31, 63],
                "machineQualifiedPhysicalFrames": list(range(49)),
            },
            CONDENSER: {
                "proposedHumanVisibleIntervals": [[0, 95]],
                "initialEntryFrameSet": [31, 63],
                "machineQualifiedPhysicalFrames": list(range(49)),
            },
        }
    }
    path = stage4._write_orbit_review_page(tmp_path, report)
    html = path.read_text(encoding="utf-8")
    assert "body{font:16px/1.6 system-ui" in html
    assert "[31, 63]" in html


def test_surface_anchor_precheck_contract_is_bounded_zero_render_and_reuses_o1():
    assert stage4.SURFACE_ANCHOR_PRECHECK == {
        "schema": "twinkle-stage4-surface-anchor-precheck-v1",
        "maximumSubmittedCandidatesPerUnit": 3,
        "maximumRaycastTrianglesPerUnit": 96,
        "barycentricCoordinates": [1 / 3, 1 / 3, 1 / 3],
        "safeBounds": [0.05, 0.05, 0.69, 0.95],
        "facingDotMinimumExclusive": 0.0,
        "surfaceHitToleranceM": 0.0001,
        "physicalFrameCount": 49,
        "logicalIndexCount": 96,
        "renderedFrameCount": 0,
        "reusedOrbitPngCount": 49,
        "totalStage4RenderedToDate": 64,
    }
    source = inspect.getsource(stage4.surface_anchor_precheck_worker)
    assert "scene.ray_cast" in source
    assert "load_camera_projection_module" in source
    assert "bpy.ops.render" not in source
    assert "save_mainfile" not in source


def test_surface_anchor_precheck_assets_are_exact_and_preserve_narrow_human_gate():
    manifest_path = SURFACE_ANCHOR_PRECHECK_OUTPUT / "surface-anchor-precheck-manifest.json"
    assert manifest_path.is_file(), "surface anchor precheck manifest is missing"
    report = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert report["schema"] == "twinkle-stage4-surface-anchor-precheck-v1"
    assert report["contract"] == stage4.SURFACE_ANCHOR_PRECHECK
    assert report["physicalFrameCount"] == 49
    assert report["logicalIndexCount"] == 96
    assert report["logicalPhysicalFrames"] == list(stage4.expanded_physical_frames())
    assert report["renderedFrameCount"] == 0
    assert report["reusedOrbitPngCount"] == 49
    assert report["totalStage4RenderedToDate"] == 64
    assert len(report["reusedOrbitPngSha256"]) == 49
    assert set(report["candidatesByUnit"]) == {CHAMBER, CONDENSER}

    required_candidate_fields = {
        "candidateId",
        "semanticId",
        "objectName",
        "meshTopologySha256",
        "polygonIndex",
        "loopTriangleIndex",
        "vertexIndices",
        "barycentricCoordinates",
        "localPosition",
        "worldPosition",
        "localNormal",
        "worldNormal",
        "positionEvaluationMethod",
        "normalEvaluationMethod",
        "candidateBlendSha256",
        "topologyAmbiguous",
        "hitAmbiguous",
        "physicalFrames",
        "logicalFrames",
        "machineQualifiedPhysicalFrames",
        "machineQualifiedLogicalFrames",
        "machineQualifiedPhysicalIntervals",
        "machineQualifiedLogicalIntervals",
        "humanApproved",
    }
    for unit in (CHAMBER, CONDENSER):
        candidates = report["candidatesByUnit"][unit]
        assert 1 <= len(candidates) <= 3
        assert report["recommendedCandidateByUnit"][unit] in {
            candidate["candidateId"] for candidate in candidates
        }
        for candidate in candidates:
            assert required_candidate_fields <= set(candidate)
            assert candidate["semanticId"] == unit
            assert len(candidate["vertexIndices"]) == 3
            assert candidate["barycentricCoordinates"] == pytest.approx(
                [1 / 3, 1 / 3, 1 / 3]
            )
            assert candidate["candidateBlendSha256"] == (
                stage4.EXPECTED_CANDIDATE_BLEND_SHA256
            )
            assert candidate["topologyAmbiguous"] is False
            assert candidate["hitAmbiguous"] is False
            assert len(candidate["physicalFrames"]) == 49
            assert len(candidate["logicalFrames"]) == 96
            assert len(set(candidate["machineQualifiedPhysicalFrames"])) >= 2
            assert candidate["machineQualifiedPhysicalIntervals"]
            assert candidate["machineQualifiedLogicalIntervals"]
    assert report["selectedCandidateByUnit"] == {
        CHAMBER: "chamber-surface-02",
        CONDENSER: "condenser-surface-01",
    }
    for unit, candidates in report["candidatesByUnit"].items():
        assert [
            candidate["candidateId"]
            for candidate in candidates
            if candidate["humanApproved"]
        ] == [report["selectedCandidateByUnit"][unit]]

    assert report["humanSurfaceApproved"] is True
    assert report["humanVisualApproved"] is False
    assert report["authorizesOrbitRepair"] is False
    assert report["authorizesStep6"] is False
    assert report["authorizesStage5"] is False
    assert report["renderOperatorInvoked"] is False
    assert report["restoration"] == {
        "candidateBlendSha256Before": stage4.EXPECTED_CANDIDATE_BLEND_SHA256,
        "candidateBlendSha256After": stage4.EXPECTED_CANDIDATE_BLEND_SHA256,
        "candidateBlendSaved": False,
        "sceneFrameRestored": True,
        "sceneCameraRestored": True,
        "sceneVisibilityRestored": True,
        "temporaryDataBlocksRemaining": [],
    }
    required_assets = {
        "surface-candidates.json",
        "frame-qualification.json",
        "logical-index-map.json",
        "raycast-summary.json",
        "surface-anchor-candidate-contact-sheet.png",
        "review/index.html",
        "worker-audit.json",
    }
    assert required_assets <= set(report["inventorySha256"])
    inventory = {
        path.relative_to(SURFACE_ANCHOR_PRECHECK_OUTPUT).as_posix(): stage4.sha256(path)
        for path in sorted(SURFACE_ANCHOR_PRECHECK_OUTPUT.rglob("*"))
        if path.is_file() and path != manifest_path
    }
    assert inventory == report["inventorySha256"]


def test_surface_anchor_review_html_treats_css_braces_as_literal_text(tmp_path):
    report = {
        "recommendedCandidateByUnit": {
            CHAMBER: "chamber-surface-01",
            CONDENSER: "condenser-surface-01",
        },
        "candidatesByUnit": {
            CHAMBER: [
                {
                    "candidateId": "chamber-surface-01",
                    "objectName": "Side2_optics :: 实体1",
                    "machineQualifiedPhysicalIntervals": [[0, 48]],
                }
            ],
            CONDENSER: [
                {
                    "candidateId": "condenser-surface-01",
                    "objectName": "ACL25416U_MOUNT_Red2 :: 实体1",
                    "machineQualifiedPhysicalIntervals": [[0, 48]],
                }
            ],
        },
    }
    path = stage4._write_surface_anchor_review(tmp_path, report)
    html = path.read_text(encoding="utf-8")
    assert "body{font:16px/1.6 system-ui" in html
    assert "chamber-surface-01" in html
    assert "condenser-surface-01" in html


def test_surface_anchor_recovery_reuses_the_completed_zero_render_worker(tmp_path):
    recovery_staging = tmp_path / ".surface-anchor-precheck-recovery"
    shutil.copytree(SURFACE_ANCHOR_PRECHECK_OUTPUT, recovery_staging)
    (recovery_staging / "surface-anchor-precheck-manifest.json").unlink()
    (recovery_staging / "review" / "index.html").unlink()
    recovery = stage4.validate_surface_anchor_precheck_recovery_staging(
        recovery_staging
    )
    assert recovery == {
        "workerSchema": "twinkle-stage4-surface-anchor-precheck-worker-v1",
        "renderOperatorInvoked": False,
        "cameraTransformCount": 49,
        "candidateCountByUnit": {CHAMBER: 3, CONDENSER: 3},
    }
    assert "recovery_staging" in inspect.signature(
        stage4.build_surface_anchor_precheck
    ).parameters


def test_surface_approval_selects_only_two_locations_and_authorizes_nothing_else(
    tmp_path,
):
    output_root = tmp_path / "surface-anchor-precheck-r1"
    shutil.copytree(SURFACE_ANCHOR_PRECHECK_OUTPUT, output_root)
    manifest_path = output_root / "surface-anchor-precheck-manifest.json"
    pending = json.loads(manifest_path.read_text(encoding="utf-8"))
    pending["humanSurfaceApproved"] = False
    pending.pop("selectedCandidateByUnit", None)
    pending.pop("surfaceApproval", None)
    for candidates in pending["candidatesByUnit"].values():
        for candidate in candidates:
            candidate["humanApproved"] = False
    manifest_path.write_text(
        json.dumps(pending, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    before = {
        path.relative_to(output_root).as_posix(): stage4.sha256(path)
        for path in output_root.rglob("*")
        if path.is_file() and path.name != "surface-anchor-precheck-manifest.json"
    }
    report = stage4.record_surface_anchor_approval(
        output_root,
        selected_candidate_by_unit={
            CHAMBER: "chamber-surface-02",
            CONDENSER: "condenser-surface-01",
        },
        approved_on="2026-08-29",
    )
    assert report["humanSurfaceApproved"] is True
    assert report["selectedCandidateByUnit"] == {
        CHAMBER: "chamber-surface-02",
        CONDENSER: "condenser-surface-01",
    }
    assert report["surfaceApproval"] == {
        "approvedBy": "user",
        "approvedOn": "2026-08-29",
        "scope": "stage4-step5-cad-surface-binding-locations-only",
        "selectedCandidateByUnit": {
            CHAMBER: "chamber-surface-02",
            CONDENSER: "condenser-surface-01",
        },
        "authorizesOrbitRepair": False,
        "authorizesStep6": False,
        "authorizesStage5": False,
    }
    for unit, candidates in report["candidatesByUnit"].items():
        approved = [
            candidate["candidateId"]
            for candidate in candidates
            if candidate["humanApproved"]
        ]
        assert approved == [report["selectedCandidateByUnit"][unit]]
    assert report["humanVisualApproved"] is False
    assert report["authorizesOrbitRepair"] is False
    assert report["authorizesStep6"] is False
    assert report["authorizesStage5"] is False
    after = {
        path.relative_to(output_root).as_posix(): stage4.sha256(path)
        for path in output_root.rglob("*")
        if path.is_file() and path.name != "surface-anchor-precheck-manifest.json"
    }
    assert after == before
    with pytest.raises(ValueError, match="already recorded"):
        stage4.record_surface_anchor_approval(
            output_root,
            selected_candidate_by_unit=report["selectedCandidateByUnit"],
            approved_on="2026-08-29",
        )


def test_c360_f96_profile_is_full_cyclic_without_duplicate_endpoint():
    assert stage4.C360_F96_PROFILE == {
        "id": "C360-F96",
        "topology": "cyclic",
        "azimuthDegrees": [0.0, 360.0],
        "endExclusive": True,
        "elevationMode": "fixed",
        "durationMs": 8_000,
        "physicalFrameCount": 96,
        "logicalIndexCount": 96,
        "angleStepDegrees": 3.75,
        "maximumTurnDurationMs": 2_000,
        "maximumAngularSpeedDegreesPerSecond": 90.0,
        "accelerationRampMs": 250,
        "decelerationRampMs": 250,
        "settledHoldMs": 100,
        "maximumEntryFramesPerUnit": 2,
    }
    angles = stage4.c360_f96_angles()
    assert len(angles) == len(set(angles)) == 96
    assert angles[0] == 0.0
    assert angles[-1] == 356.25
    assert 360.0 not in angles
    assert all(
        (angles[(index + 1) % 96] - angles[index]) % 360.0 == 3.75
        for index in range(96)
    )


def test_c360_entry_selection_adds_only_one_auxiliary_to_meet_wait_limit():
    qualified = list(range(96))
    result = stage4.select_c360_entry_frames(
        qualified,
        hero_frame=0,
        frame_count=96,
        recognizable_frames=list(range(96)),
    )
    assert result["entryFrameSet"] == [0, 48]
    assert result["maximumCyclicDistanceFrames"] == 24
    assert result["maximumCyclicDistanceDegrees"] == 90.0
    assert result["auxiliaryEntryAdded"] is True
    assert result["recognizabilityGateApplied"] is True


def test_c360_entry_selection_fails_closed_without_recognizable_candidates():
    with pytest.raises(ValueError, match="recognizable entry candidate"):
        stage4.select_c360_entry_frames(
            [8, 87],
            hero_frame=8,
            frame_count=96,
            recognizable_frames=[],
        )
    with pytest.raises(ValueError, match="machine qualified"):
        stage4.select_c360_entry_frames(
            [8, 87],
            hero_frame=8,
            frame_count=96,
            recognizable_frames=[8, 88],
        )


def test_c360_entry_selection_uses_only_component_recognizability_pool():
    result = stage4.select_c360_entry_frames(
        list(range(96)),
        hero_frame=83,
        frame_count=96,
        recognizable_frames=[62, 83],
    )
    assert result["entryFrameSet"] == [83, 62]
    assert result["maximumCyclicDistanceFrames"] == 37
    assert result["maximumCyclicDistanceDegrees"] == 138.75
    assert result["auxiliaryEntryAdded"] is True
    assert result["recognizabilityGateApplied"] is True


def test_c360_component_recognizability_uses_complete_overview_projection():
    report = json.loads(
        (C360_F96_OUTPUT / "orbit-c360-f96-manifest.json").read_text(
            encoding="utf-8"
        )
    )
    chamber_clear = stage4.c360_component_recognizability_record(
        CHAMBER, report["frames"][6]
    )
    chamber_narrow = stage4.c360_component_recognizability_record(
        CHAMBER, report["frames"][11]
    )
    condenser_boundary = stage4.c360_component_recognizability_record(
        CONDENSER, report["frames"][87]
    )

    assert chamber_clear["authorityState"] == "complete-overview-assembly"
    assert chamber_clear["usesFocusOrExtractState"] is False
    assert chamber_clear["projectionMethod"] == (
        "twinkle_camera_projection-authority-hull"
    )
    assert chamber_clear["gatePassed"] is True
    assert chamber_narrow["gatePassed"] is False
    assert chamber_narrow["criteria"]["minimumVisibleWidth"] is False
    assert condenser_boundary["gatePassed"] is True
    for record in (chamber_clear, chamber_narrow, condenser_boundary):
        assert record["visibleFraction"] == pytest.approx(1.0)
        assert record["hotspotStatus"] in {
            "visible",
            "back-facing",
            "occluded",
            "out-of-safe",
        }
        assert record["thresholds"] == (
            stage4.C360_F96_COMPONENT_RECOGNIZABILITY[record["semanticId"]]
        )


def test_c360_name_button_turn_plan_meets_time_and_velocity_caps():
    plan = stage4.plan_c360_shortest_turn(
        current_frame=47,
        entry_frames=[8, 87],
        orbit_direction="forward",
    )
    assert plan == {
        "selectedEntryFrame": 8,
        "direction": "backward",
        "distanceFrames": 39,
        "distanceDegrees": 146.25,
        "accelerationRampMs": 250,
        "decelerationRampMs": 250,
        "settledHoldMs": 100,
        "turnDurationMs": 1_975,
        "peakAngularSpeedDegreesPerSecond": 90.0,
        "arrivesStopped": True,
        "enterFocusAfterSettled": True,
    }


def test_c360_recovery_reuses_exactly_96_rendered_frames(tmp_path):
    recovery_staging = tmp_path / ".orbit-c360-f96-recovery"
    shutil.copytree(C360_F96_OUTPUT, recovery_staging)
    for path in sorted(recovery_staging.rglob("*"), reverse=True):
        if path.is_file() and not (
            path.name == "worker-audit.json" or path.parent.name == "frames"
        ):
            path.unlink()
    recovery = stage4.validate_c360_f96_recovery_staging(
        recovery_staging
    )
    assert recovery == {
        "workerSchema": "twinkle-stage4-c360-f96-worker-v1",
        "renderedFrameCount": 96,
        "frameCount": 96,
        "candidateBlendSaved": False,
    }
    assert "recovery_staging" in inspect.signature(stage4.build_c360_f96).parameters


def test_c360_review_refresh_changes_only_zero_render_derived_audit_files(
    tmp_path,
):
    target = tmp_path / "orbit-c360-f96-r1"
    shutil.copytree(C360_F96_OUTPUT, target)
    manifest_path = target / "orbit-c360-f96-manifest.json"
    pending = json.loads(manifest_path.read_text(encoding="utf-8"))
    pending["humanVisualApproved"] = False
    pending["humanEntryApproved"] = False
    pending.pop("c360ReviewApproval", None)
    for qualification in pending["qualificationByUnit"].values():
        qualification["humanEntryApproved"] = False
        qualification["humanApproved"] = False
        for candidate in qualification["entryCandidates"]:
            candidate["componentRecognizability"][
                "humanReviewStatus"
            ] = "pending"
    manifest_path.write_text(
        json.dumps(pending, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    immutable = {
        path.relative_to(target).as_posix(): stage4.sha256(path)
        for path in target.rglob("*")
        if path.is_file()
        and path.relative_to(target).as_posix()
        not in {
            "frame-qualification.json",
            "review/index.html",
            "review/review-data.json",
            "orbit-c360-f96-manifest.json",
        }
    }
    report = stage4.refresh_c360_f96_review(target)
    after = {
        path.relative_to(target).as_posix(): stage4.sha256(path)
        for path in target.rglob("*")
        if path.is_file()
        and path.relative_to(target).as_posix()
        not in {
            "frame-qualification.json",
            "review/index.html",
            "review/review-data.json",
            "orbit-c360-f96-manifest.json",
        }
    }
    assert after == immutable
    assert report["reviewOptimization"]["renderedFrameCount"] == 0
    assert report["reviewOptimization"]["sourcePngAndWorkerAuditUnchanged"] is True
    assert report["reviewOptimization"]["surfaceState"] == (
        "complete-overview-assembly"
    )


def test_c360_human_review_approval_is_bound_to_reviewed_scope_only(tmp_path):
    output_root = tmp_path / "orbit-c360-f96-r1"
    shutil.copytree(C360_F96_OUTPUT, output_root)
    manifest_path = output_root / "orbit-c360-f96-manifest.json"
    pending = json.loads(manifest_path.read_text(encoding="utf-8"))
    pending["humanVisualApproved"] = False
    pending["humanEntryApproved"] = False
    pending.pop("c360ReviewApproval", None)
    for qualification in pending["qualificationByUnit"].values():
        qualification["humanEntryApproved"] = False
        qualification["humanApproved"] = False
        for candidate in qualification["entryCandidates"]:
            candidate["componentRecognizability"][
                "humanReviewStatus"
            ] = "pending"
    manifest_path.write_text(
        json.dumps(pending, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    before = {
        path.relative_to(output_root).as_posix(): stage4.sha256(path)
        for path in output_root.rglob("*")
        if path.is_file() and path.name != "orbit-c360-f96-manifest.json"
    }

    report = stage4.record_c360_f96_review_approval(
        output_root, approved_on="2026-08-30"
    )

    assert report["humanVisualApproved"] is True
    assert report["humanEntryApproved"] is True
    assert report["c360ReviewApproval"] == {
        "approvedBy": "user",
        "approvedOn": "2026-08-30",
        "scope": (
            "stage4-c360-f96-visual-hotspots-visible-intervals-and-"
            "overview-exit-entry-candidates-only"
        ),
        "approvedReviewAsset": "review/index.html",
        "approvedReviewAssetSha256": before["review/index.html"],
        "approvedVisibleIntervalsByUnit": {
            CHAMBER: [{"start": 62, "end": 11, "wraps": True}],
            CONDENSER: [{"start": 87, "end": 8, "wraps": True}],
        },
        "approvedEntryFrameSetByUnit": {
            CHAMBER: [6, 65],
            CONDENSER: [87, 8],
        },
        "authorizesOrbitRepair": False,
        "authorizesStep6": False,
        "authorizesStage5": False,
    }
    assert report["authorizesOrbitRepair"] is False
    assert report["authorizesStep6"] is False
    assert report["authorizesStage5"] is False
    assert all(
        qualification["humanEntryApproved"] is True
        and qualification["humanApproved"] is True
        and all(
            candidate["componentRecognizability"]["humanReviewStatus"]
            == "approved"
            for candidate in qualification["entryCandidates"]
        )
        for qualification in report["qualificationByUnit"].values()
    )
    after = {
        path.relative_to(output_root).as_posix(): stage4.sha256(path)
        for path in output_root.rglob("*")
        if path.is_file() and path.name != "orbit-c360-f96-manifest.json"
    }
    assert after == before
    with pytest.raises(ValueError, match="already recorded"):
        stage4.record_c360_f96_review_approval(
            output_root, approved_on="2026-08-30"
        )


def test_c360_f96_candidate_has_dynamic_review_and_approved_human_gate():
    manifest_path = C360_F96_OUTPUT / "orbit-c360-f96-manifest.json"
    assert manifest_path.is_file(), "C360-F96 manifest is missing"
    report = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert report["schema"] == "twinkle-stage4-orbit-c360-f96-v1"
    assert report["orbitProfile"] == stage4.C360_F96_PROFILE
    assert report["anglesDegrees"] == stage4.c360_f96_angles()
    assert report["physicalFrameCount"] == 96
    assert report["logicalIndexCount"] == 96
    assert report["logicalPhysicalFrames"] == list(range(96))
    assert report["renderedFrameCount"] == 96
    assert report["totalStage4RenderedToDate"] == 160
    assert report["selectedSurfaceAnchorByUnit"] == {
        CHAMBER: "chamber-surface-02",
        CONDENSER: "condenser-surface-01",
    }
    assert len(report["frames"]) == 96
    assert [frame["physicalFrameIndex"] for frame in report["frames"]] == list(
        range(96)
    )
    assert len(list((C360_F96_OUTPUT / "frames").glob("frame-*.png"))) == 96
    assert all(frame["quality"]["blackFrame"] is False for frame in report["frames"])
    assert all(frame["quality"]["emptyFrame"] is False for frame in report["frames"])
    assert all(frame["targetClipped"] is False for frame in report["frames"])
    assert all(frame["subjectOutOfFrame"] is False for frame in report["frames"])
    assert report["closureMetrics"]["duplicateEndpointRendered"] is False
    assert report["closureMetrics"]["seamPositionStepRatio"] <= 1.05
    assert report["closureMetrics"]["seamOrientationStepRatio"] <= 1.05
    assert report["closureMetrics"]["pixelSeamRatio"] <= 1.25

    statuses = {"visible", "back-facing", "occluded", "out-of-safe"}
    expected_entries = {CHAMBER: [6, 65], CONDENSER: [87, 8]}
    assert set(report["qualificationByUnit"]) == {CHAMBER, CONDENSER}
    for unit in (CHAMBER, CONDENSER):
        qualification = report["qualificationByUnit"][unit]
        assert len(qualification["physicalFrames"]) == 96
        assert len(qualification["logicalFrames"]) == 96
        assert set(frame["status"] for frame in qualification["physicalFrames"]) <= statuses
        assert qualification["machineQualifiedPhysicalFrames"]
        assert qualification["machineQualifiedCyclicIntervals"]
        assert qualification["initialEntryFrameSet"] == expected_entries[unit]
        assert qualification["componentRecognizabilityGateOrder"] == [
            "machine-visible",
            "complete-overview-component-projection",
            "cyclic-shortest-turn",
        ]
        assert qualification["componentRecognizabilityQualifiedFrames"]
        assert qualification["entrySelection"]["recognizabilityGateApplied"] is True
        assert qualification["entryRole"] == "overview-exit-only"
        assert qualification["focusRouteGenerated"] is False
        assert qualification["humanEntryApproved"] is True
        assert len(qualification["entryCandidates"]) == len(
            qualification["initialEntryFrameSet"]
        )
        assert [
            candidate["frameIndex"]
            for candidate in qualification["entryCandidates"]
        ] == qualification["initialEntryFrameSet"]
        for candidate in qualification["entryCandidates"]:
            assert candidate["frameIndex"] in qualification[
                "machineQualifiedPhysicalFrames"
            ]
            assert candidate["sourcePng"].startswith("frames/frame-")
            assert candidate["hotspotStatus"] == "visible"
            recognizability = candidate["componentRecognizability"]
            assert recognizability["gatePassed"] is True
            assert recognizability["authorityState"] == (
                "complete-overview-assembly"
            )
            assert recognizability["usesFocusOrExtractState"] is False
            assert recognizability["hotspotStatus"] == "visible"
            assert all(recognizability["criteria"].values())
            assert recognizability["humanReviewStatus"] == "approved"
            assert candidate["visualCueZh"]
        assert qualification["entrySelection"]["maximumCyclicDistanceFrames"] <= 48
        assert qualification["turnPlanWorstCase"]["turnDurationMs"] <= 2_000
        assert (
            qualification["turnPlanWorstCase"][
                "peakAngularSpeedDegreesPerSecond"
            ]
            <= 90.0
        )
        assert qualification["turnPlanWorstCase"]["arrivesStopped"] is True
        assert qualification["turnPlanWorstCase"]["enterFocusAfterSettled"] is True
        assert qualification["humanApproved"] is True

    html = (C360_F96_OUTPUT / "review" / "index.html").read_text(
        encoding="utf-8"
    )
    for token in (
        '<link rel="icon" href="data:,">',
        'data-testid="spin-player"',
        'data-testid="play-pause"',
        'data-testid="replay"',
        'data-testid="scrubber"',
        'data-testid="frame-status"',
        'data-action-unit="dual_channel_collection_optics_chamber"',
        'data-action-unit="dual_channel_condenser_lens_assembly"',
        "双通道采集光学舱",
        "聚光镜组件",
        "--hotspot:#fff",
        "--hotspot-fade:140ms",
        "visible",
        "back-facing",
        "occluded",
        "准备进入聚焦",
        "入口帧只是总览出口",
        "focusRouteGenerated:false",
        "pointer-events:none",
        "hotspot-label",
        ".hotspot-label{opacity:1;transform:translate(0,-50%);pointer-events:none}",
        "el.disabled=!isVisible",
        "aria-hidden",
        "scheduleHotspotVisibility",
        "void el.offsetWidth",
        "el.hidden=true",
        ".hotspot.is-visible{opacity:1}",
        "function preloadFrames()",
        "Promise.all(data.frames.map",
        "人工审核控制栏",
        "不实现正式详情面板、产品讲解内容、阶段 3 动作接入、生产信息架构或生产页面交互",
    ):
        assert token in html
    assert '<button class="hotspot' in html
    assert "#FFB000" not in html
    assert "#00C2FF" not in html
    assert ".hotspot.chamber{" not in html
    assert ".hotspot.condenser{" not in html
    assert "可进入${names[unit]}聚焦路线" not in html
    assert "hotspot.back-facing{opacity" not in html
    assert "hotspot.occluded{opacity" not in html
    assert report["reviewPlayer"] == {
        "asset": "review/index.html",
        "durationMs": 8_000,
        "playsExactlyOneCycle": True,
        "supportsPlayPauseResume": True,
        "supportsReplay": True,
        "supportsScrubbing": True,
        "supportsNameButtonNavigation": True,
        "maximumTurnDurationMs": 2_000,
        "maximumAngularSpeedDegreesPerSecond": 90.0,
        "entersFocusOnlyAfterSettled": True,
        "focusReadyLabel": "准备进入聚焦",
        "entryRole": "overview-exit-only",
        "focusRouteGenerated": False,
        "componentRecognizabilityGate": True,
        "nonVisibleHotspotsHiddenAndNonInteractive": True,
        "hotspotLabelsShownWheneverVisible": True,
        "unifiedModelHotspotColor": "#FFFFFF",
        "hotspotVisibilityTransitionMs": 140,
        "usesRapidHotspotFadeInOut": True,
        "preloadsAllSourceFrames": True,
        "hotspotsAreHtmlOverlays": True,
        "sourcePngPixelsModified": False,
    }
    assert report["staticContactSheet"]["sampledFrameIndices"] == list(
        range(0, 96, 8)
    )
    assert report["machinePassed"] is True
    assert report["humanVisualApproved"] is True
    assert report["humanEntryApproved"] is True
    assert report["c360ReviewApproval"]["approvedOn"] == "2026-08-30"
    assert report["c360ReviewApproval"]["approvedReviewAssetSha256"] == (
        report["inventorySha256"]["review/index.html"]
    )
    assert report["authorizesOrbitRepair"] is False
    assert report["authorizesStep6"] is False
    assert report["authorizesStage5"] is False
    assert report["budgetEvidence"]["renderedThisRun"] == 96
    assert report["budgetEvidence"]["totalRenderedToDate"] == 160
    assert report["inventorySha256"] == {
        path.relative_to(C360_F96_OUTPUT).as_posix(): stage4.sha256(path)
        for path in sorted(C360_F96_OUTPUT.rglob("*"))
        if path.is_file() and path != manifest_path
    }


def test_c360_auxiliary_contact_sheet_uses_readable_three_line_cells():
    with Image.open(
        C360_F96_OUTPUT / "c360-f96-12-frame-contact-sheet.png"
    ) as sheet:
        assert sheet.size == (1280, 891)
    source = inspect.getsource(stage4._write_c360_contact_sheet)
    assert 'CHAMBER: "光学舱"' in source
    assert 'CONDENSER: "聚光镜"' in source
    assert '"visible": "可见"' in source


@pytest.mark.parametrize("playback", ["running", "paused"])
def test_step6_frame_qualification_keeps_name_buttons_available_in_global(playback):
    report = json.loads(
        (C360_F96_OUTPUT / "orbit-c360-f96-manifest.json").read_text(
            encoding="utf-8"
        )
    )
    hidden_frame = next(
        frame["physicalFrameIndex"]
        for frame in report["qualificationByUnit"][CHAMBER]["physicalFrames"]
        if not frame["machineQualified"]
    )
    controls = stage4.c360_global_controls(
        report, orbit_frame_index=hidden_frame, orbit_playback=playback
    )

    assert controls["modelHotspots"][CHAMBER] == {
        "visible": False,
        "enabled": False,
    }
    assert controls["unitNames"] == {
        CHAMBER: {"visible": True, "enabled": True},
        CONDENSER: {"visible": True, "enabled": True},
    }
    assert controls["globalToggle"]["label"] == (
        "暂停展示" if playback == "running" else "开始展示"
    )


def test_step6_name_entry_uses_nearest_cyclic_entry_and_direction_tie():
    trace = stage4.build_c360_focus_trace(
        unit=CHAMBER,
        source="name",
        current_frame=38,
        orbit_direction="forward",
        entry_frames=[6, 70],
        curve_frame_indices=["stub-curve-000", "stub-curve-001"],
        model_hotspot_qualified=False,
    )

    assert trace["selectedEntryFrame"] == 70
    assert trace["capturedOrbitFrame"] == 38
    assert trace["capturedOrbitDirection"] == "forward"
    assert trace["orbitPrefixIndices"] == list(range(38, 71))
    assert trace["curveFrameIndices"] == ["stub-curve-000", "stub-curve-001"]

    tie = stage4.build_c360_focus_trace(
        unit=CHAMBER,
        source="name",
        current_frame=38,
        orbit_direction="backward",
        entry_frames=[6, 70],
        curve_frame_indices=["stub-curve-000"],
        model_hotspot_qualified=False,
    )
    assert tie["selectedEntryFrame"] == 6
    assert tie["orbitPrefixIndices"] == list(range(38, 5, -1))


def test_step6_model_hotspot_hidden_is_noop_but_qualified_click_builds_trace():
    hidden = stage4.build_c360_focus_trace(
        unit=CONDENSER,
        source="model",
        current_frame=40,
        orbit_direction="forward",
        entry_frames=[8, 87],
        curve_frame_indices=["stub-focus-000", "stub-focus-001"],
        model_hotspot_qualified=False,
    )
    assert hidden is None

    qualified = stage4.build_c360_focus_trace(
        unit=CONDENSER,
        source="model",
        current_frame=40,
        orbit_direction="forward",
        entry_frames=[8, 87],
        curve_frame_indices=["stub-focus-000", "stub-focus-001"],
        model_hotspot_qualified=True,
    )
    assert qualified["selectedEntryFrame"] == 8
    assert qualified["fullFocusTrace"] == (
        qualified["orbitPrefixIndices"] + qualified["curveFrameIndices"]
    )
    assert qualified["overviewReturn"] == list(
        reversed(qualified["fullFocusTrace"])
    )


@pytest.mark.parametrize("phase", ["focus", "expand", "close", "overviewReturn"])
def test_step6_pause_and_resume_hold_exact_point_and_direction(phase):
    state = stage4.trace_playback_state(
        phase=phase,
        trace=["frame-0", "frame-1", "frame-2"],
        cursor=1,
        direction="backward" if phase in {"close", "overviewReturn"} else "forward",
    )
    paused = stage4.set_trace_playback(state, "paused")
    resumed = stage4.set_trace_playback(paused, "running")

    assert paused["cursor"] == resumed["cursor"] == 1
    assert paused["currentPoint"] == resumed["currentPoint"] == "frame-1"
    assert paused["direction"] == resumed["direction"] == state["direction"]
    assert paused["playback"] == "paused"
    assert resumed["playback"] == "running"


def test_step6_entry_removal_invalidates_only_dependent_trace_and_cache():
    traces = {
        "chamber-6-A": {"unit": CHAMBER, "selectedEntryFrame": 6},
        "chamber-65-B": {"unit": CHAMBER, "selectedEntryFrame": 65},
        "condenser-8-A": {"unit": CONDENSER, "selectedEntryFrame": 8},
    }
    cache = {key: f"cached-{key}" for key in traces}

    result = stage4.invalidate_entry_frame(
        entry_frames_by_unit={CHAMBER: [6, 65], CONDENSER: [87, 8]},
        traces=traces,
        cache=cache,
        unit=CHAMBER,
        removed_entry_frame=6,
    )

    assert result["entryFramesByUnit"] == {
        CHAMBER: [65],
        CONDENSER: [87, 8],
    }
    assert result["invalidatedTraceIds"] == ["chamber-6-A"]
    assert set(result["traces"]) == {"chamber-65-B", "condenser-8-A"}
    assert set(result["cache"]) == {"chamber-65-B", "condenser-8-A"}


def test_step6_strict_return_finishes_at_capture_in_global_paused():
    trace = stage4.build_c360_focus_trace(
        unit=CHAMBER,
        source="name",
        current_frame=95,
        orbit_direction="forward",
        entry_frames=[6, 65],
        curve_frame_indices=["stub-curve-000", "stub-curve-001"],
        model_hotspot_qualified=False,
    )
    completed = stage4.complete_c360_overview_return(trace)

    assert completed == {
        "topLevel": "global",
        "orbitTopology": "cyclic",
        "orbitFrameIndex": 95,
        "orbitDirection": "forward",
        "orbitPlayback": "paused",
        "globalOrbit": "paused",
    }


def test_step7_c1_profile_is_keyframe_only_and_cannot_masquerade_as_c2():
    assert stage4.C1_KEYFRAME_PROFILE == {
        "schema": "twinkle-stage4-c1-keyframe-precheck-v1",
        "curveSampleCount": 25,
        "previewSampleIndices": [0, 12, 24],
        "newRenderSampleIndices": [12],
        "durationMs": 1_000,
        "settledHoldMs": 100,
        "variants": ["A", "B"],
        "orientationConstraint": "TRACK_TO",
        "render": {"resolution": [640, 450], "samples": 64, "format": "PNG"},
        "fullSequenceGenerated": False,
        "stage3MechanicalPlaybackGenerated": False,
        "reusesApprovedEndpoints": True,
    }


def test_step7_c1_routes_differ_only_in_shape_and_join_approved_endpoints():
    orbit = json.loads(
        (C360_F96_OUTPUT / "orbit-c360-f96-manifest.json").read_text(
            encoding="utf-8"
        )
    )
    authority = stage4.validate_authority()["stage1"]
    routes = stage4.c1_route_contracts(orbit, authority)

    assert len(routes) == 8
    assert {
        (route["unit"], route["entryFrame"], route["variant"])
        for route in routes
    } == {
        (unit, entry, variant)
        for unit, entries in {
            CHAMBER: [6, 65],
            CONDENSER: [87, 8],
        }.items()
        for entry in entries
        for variant in ("A", "B")
    }
    for unit, entries in {CHAMBER: [6, 65], CONDENSER: [87, 8]}.items():
        for entry in entries:
            pair = [
                route
                for route in routes
                if route["unit"] == unit and route["entryFrame"] == entry
            ]
            assert [route["variant"] for route in pair] == ["A", "B"]
            assert pair[0]["commonFields"] == pair[1]["commonFields"]
            assert pair[0]["curveControlPoints"] != pair[1]["curveControlPoints"]
            for route in pair:
                assert len(route["curveSamplePositions"]) == 25
                assert route["curveSamplePositions"][0] == pytest.approx(
                    route["commonFields"]["startLocation"], abs=1e-8
                )
                assert route["curveSamplePositions"][-1] == pytest.approx(
                    route["commonFields"]["endLocation"], abs=1e-8
                )
                assert route["commonFields"]["entryApproved"] is True
                assert route["commonFields"]["mechanicalStartsAfterSettled"] is True
                assert route["commonFields"]["fullSequenceGenerated"] is False


def test_step7_follow_path_midpoint_uses_polyline_arc_length_fraction():
    samples = [[0.0, 0.0, 0.0], [9.0, 0.0, 0.0], [10.0, 0.0, 0.0]]
    offsets = stage4.polyline_offset_factors(samples)
    assert offsets == pytest.approx([0.0, 0.9, 1.0])
    assert offsets[1] != 0.5


def test_step7_c1_blender_command_is_background_and_fail_closed(tmp_path):
    command = stage4.c1_keyframe_blender_command(
        Path("blender.exe"),
        tmp_path / "candidate.blend",
        tmp_path / "staging",
    )
    assert command[:3] == [
        "blender.exe",
        "--background",
        str(tmp_path / "candidate.blend"),
    ]
    assert command[command.index("--python-exit-code") + 1] == "1"
    assert "--stage4-c1-keyframe-worker" in command
    assert command[-1] == str(tmp_path / "staging")


def test_step7_c1_output_parent_can_retain_failed_isolated_staging(tmp_path):
    parent = tmp_path / ".twinkle-stage4-c1-keyframe-precheck-20260830"
    parent.mkdir()
    (parent / ".c1-keyframes-retained-failure").mkdir()
    output = parent / "c1-keyframe-precheck-r1"

    assert stage4.prepare_c1_output_parent(output) == parent.resolve()
    assert not output.exists()


def test_step7_c1_machine_candidate_is_keyframe_only_and_waits_for_human():
    report = stage4.validate_c1_keyframe_precheck(C1_KEYFRAME_OUTPUT)

    assert report["schema"] == "twinkle-stage4-c1-keyframe-precheck-v1"
    assert report["profile"] == stage4.C1_KEYFRAME_PROFILE
    assert report["routeCount"] == 8
    assert report["renderedFrameCount"] == 8
    assert report["reusedEndpointFrameCount"] == 16
    assert report["totalStage4RenderedToDate"] == 168
    assert report["machinePassed"] is True
    assert report["humanC1Approved"] is False
    assert report["humanVisualApproved"] is False
    assert report["authorizesStep8"] is False
    assert report["authorizesStage5"] is False
    assert report["fullSequenceGenerated"] is False
    assert report["stage3MechanicalPlaybackGenerated"] is False
    assert report["review"]["asset"] == "review/index.html"
    assert report["review"]["contactSheet"] == "review/c1-keyframes-contact-sheet.png"
    assert report["review"]["candidateGroupRepairUsedByUnit"] == {
        CHAMBER: False,
        CONDENSER: False,
    }
    for route in report["routes"]:
        assert route["previewSampleIndices"] == [0, 12, 24]
        assert len(route["previewFrames"]) == 3
        assert all(frame["blackFrame"] is False for frame in route["previewFrames"])
        assert all(frame["emptyFrame"] is False for frame in route["previewFrames"])
        assert route["machinePassed"] is True
        assert route["humanApproved"] is False
        assert route["fullSequenceGenerated"] is False
        route_dir = C1_KEYFRAME_OUTPUT / "frames" / route["routeId"]
        assert sorted(path.name for path in route_dir.glob("*.png")) == [
            "keyframe-000.png",
            "keyframe-012.png",
            "keyframe-024.png",
        ]
    pairs = {}
    for route in report["routes"]:
        pairs.setdefault((route["unit"], route["entryFrame"]), []).append(route)
    for pair in pairs.values():
        assert [route["variant"] for route in pair] == ["A", "B"]
        assert pair[0]["commonFields"] == pair[1]["commonFields"]
        assert pair[0]["curveControlPoints"] != pair[1]["curveControlPoints"]
    manifest_path = C1_KEYFRAME_OUTPUT / "c1-keyframe-precheck-manifest.json"
    assert report["inventorySha256"] == {
        path.relative_to(C1_KEYFRAME_OUTPUT).as_posix(): stage4.sha256(path)
        for path in sorted(C1_KEYFRAME_OUTPUT.rglob("*"))
        if path.is_file() and path != manifest_path
    }


def test_step8_c2_profile_requires_full_focus_real_r2_and_review_gates():
    assert stage4.C2_FULL_REVIEW_PROFILE == {
        "schema": "twinkle-stage4-c2-full-review-v1",
        "curveSampleCount": 25,
        "curveDurationMs": 1_000,
        "settledHoldMs": 100,
        "variants": ["A", "B"],
        "orientationConstraint": "TRACK_TO",
        "render": {"resolution": [640, 450], "samples": 64, "format": "PNG"},
        "stage3R2FrameCountPerUnit": 25,
        "inspectionLight": {"fadeInMs": 900, "holdMs": 500, "fadeOutMs": 700},
        "fullSequenceGenerated": True,
        "stage3MechanicalPlaybackGenerated": True,
        "overviewReturn": "strict-full-focus-trace-reverse",
        "captureFrameRequired": True,
        "staticFallbackRequired": True,
    }


def test_step8_c2_routes_bind_c1_choices_to_full_focus_and_real_r2():
    require_step8_integration_assets()
    c1 = stage4.validate_c1_keyframe_precheck(C1_KEYFRAME_OUTPUT)
    stage3 = json.loads(stage4.STAGE3_R2_MANIFEST.read_text(encoding="utf-8"))
    choices = {
        CHAMBER: {6: "A", 65: "B"},
        CONDENSER: {87: "A", 8: "A"},
    }

    routes = stage4.c2_route_contracts(c1, stage3, choices)

    assert len(routes) == 8
    assert sum(route["c1HumanChoice"] for route in routes) == 4
    capture_cases = {
        (CHAMBER, 6): (0, "forward"),
        (CHAMBER, 65): (72, "backward"),
        (CONDENSER, 87): (92, "backward"),
        (CONDENSER, 8): (3, "forward"),
    }
    for route in routes:
        assert route["c1HumanChoice"] is (
            route["variant"] == choices[route["unit"]][route["entryFrame"]]
        )
        assert route["focusSampleIndices"] == list(range(25))
        assert route["stage3R2"]["expandFrameIndices"] == list(range(25))
        assert route["stage3R2"]["closeFrameIndices"] == list(range(24, -1, -1))
        assert route["stage3R2"]["sourceManifestSha256"] == stage4.sha256(
            stage4.STAGE3_R2_MANIFEST
        )
        if route["unit"] == CHAMBER:
            assert route["stage3R2"]["inspectionLight"] == {
                "unlitAsset": "review/inspection-unlit.png",
                "litAsset": "review/inspection-lit.png",
                "fadeInMs": 900,
                "holdMs": 500,
                "fadeOutMs": 700,
            }
        else:
            assert route["stage3R2"]["inspectionLight"] is None
        captured_frame, captured_direction = capture_cases[
            (route["unit"], route["entryFrame"])
        ]
        assert route["capturedOrbitFrame"] == captured_frame
        assert route["capturedOrbitDirection"] == captured_direction
        assert route["orbitPrefixIndices"][0] == captured_frame
        assert route["orbitPrefixIndices"][-1] == route["entryFrame"]
        assert len(route["orbitPrefixIndices"]) > 1
        assert route["modelHotspotQualified"] is True
        assert route["fullFocusTrace"][0] == {
            "phase": "orbit",
            "frameIndex": captured_frame,
        }
        assert route["overviewReturn"] == list(reversed(route["fullFocusTrace"]))
        assert route["humanVisualApproved"] is False


def test_step8_c2_blender_command_is_background_and_fail_closed(tmp_path):
    command = stage4.c2_full_review_blender_command(
        Path("blender.exe"),
        tmp_path / "candidate.blend",
        tmp_path / "staging",
    )
    assert command[:3] == [
        "blender.exe",
        "--background",
        str(tmp_path / "candidate.blend"),
    ]
    assert command[command.index("--python-exit-code") + 1] == "1"
    assert "--stage4-c2-full-worker" in command
    assert command[-1] == str(tmp_path / "staging")


def test_step8_c2_build_requires_explicit_authorization(tmp_path):
    output = tmp_path / "c2-full-review-r1"
    with pytest.raises(PermissionError, match="explicit authorization"):
        stage4.build_c2_full_review(
            output,
            choices={
                CHAMBER: {6: "A", 65: "B"},
                CONDENSER: {87: "A", 8: "A"},
            },
            authorized=False,
        )
    assert not output.exists()


def test_step8_c2_quality_upgrade_requires_explicit_authorization(tmp_path):
    with pytest.raises(PermissionError, match="explicit authorization"):
        stage4.upgrade_c2_quality_bindings(
            tmp_path / "c2-full-review-r1",
            backup_root=tmp_path / "legacy-c2-backup",
            authorized=False,
        )


def test_step8_c2_builds_complete_focus_inventory_and_waits_for_browser(tmp_path):
    require_step8_integration_assets()
    output = tmp_path / "c2-full-review-r1"
    choices = {
        CHAMBER: {6: "A", 65: "B"},
        CONDENSER: {87: "A", 8: "A"},
    }

    def fake_runner(command, cwd):
        assert Path(cwd).resolve() == ROOT.resolve()
        staging = Path(command[-1])
        worker_contract = json.loads(
            (staging / "c2-worker-contracts.json").read_text(encoding="utf-8")
        )
        assert worker_contract["contractSha256"] == stage4.canonical_json_sha256(
            worker_contract["routes"]
        )
        rendered_indices = [index for index in range(25) if index not in {0, 12, 24}]
        worker_routes = []
        for route in worker_contract["routes"]:
            route_root = staging / "frames" / route["routeId"]
            route_root.mkdir(parents=True, exist_ok=True)
            records = []
            for index in rendered_indices:
                path = route_root / f"focus-{index:03d}.png"
                Image.new(
                    "RGB",
                    (640, 450),
                    (40 + index * 3, 80 + index * 2, 120 + index),
                ).save(path)
                records.append(
                    {
                        "sampleIndex": index,
                        "path": path.relative_to(staging).as_posix(),
                        "expectedPosition": route["curveSamplePositions"][index],
                        "positionErrorM": 0.0,
                        "targetErrorDegrees": 0.0,
                        "rollDegrees": 0.0,
                        "sha256": stage4.sha256(path),
                    }
                )
            worker_routes.append({"routeId": route["routeId"], "frames": records})
        (staging / "worker-audit.json").write_text(
            json.dumps(
                {
                    "schema": "twinkle-stage4-c2-full-worker-v1",
                    "contractSha256": worker_contract["contractSha256"],
                    "routes": worker_routes,
                    "renderedFrameCount": 176,
                    "restoration": {
                        "candidateBlendSaved": False,
                        "candidateBlendSha256Before": stage4.EXPECTED_CANDIDATE_BLEND_SHA256,
                        "candidateBlendSha256After": stage4.EXPECTED_CANDIDATE_BLEND_SHA256,
                        "sceneSettingsRestored": True,
                        "temporaryDataBlocksRemaining": [],
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    report = stage4.build_c2_full_review(
        output,
        choices=choices,
        authorized=True,
        blender=Path("blender.exe"),
        runner=fake_runner,
    )

    assert report["schema"] == "twinkle-stage4-c2-full-review-v1"
    assert report["routeCount"] == 8
    assert report["renderedFocusFrameCount"] == 176
    assert report["reusedC1FrameCount"] == 24
    assert report["referencedStage3R2FrameCount"] == 50
    assert report["localReviewDependencyCount"] == 75
    assert len(report["reviewAssetInventorySha256"]) == 64
    assert report["reviewPageSha256"] == stage4.sha256(output / "review/index.html")
    assert report["workerContractSha256"] == stage4.canonical_json_sha256(
        json.loads((output / "c2-worker-contracts.json").read_text(encoding="utf-8"))[
            "routes"
        ]
    )
    assert report["renderMachinePassed"] is True
    assert report["browserMachinePassed"] is False
    assert report["machinePassed"] is False
    assert report["humanVisualApproved"] is False
    assert report["authorizesStep9"] is False
    assert report["stage4Closed"] is False
    assert report["authorizesStage5"] is False
    assert report["review"] == {
        "asset": "review/index.html",
        "staticFallback": "review/c2-static-fallback.png",
    }
    html = (output / "review/index.html").read_text(encoding="utf-8")
    assert "/output/" not in html
    assert "reviewAssetInventorySha256" in html
    for route in report["routes"]:
        assert len(route["focusFrames"]) == 25
        assert [frame["sampleIndex"] for frame in route["focusFrames"]] == list(
            range(25)
        )
        assert sum(frame["provenance"] == "c2-new-render" for frame in route["focusFrames"]) == 22
        assert sum(frame["provenance"] == "approved-c1-reuse" for frame in route["focusFrames"]) == 3
        assert all(frame["blackFrame"] is False for frame in route["focusFrames"])
        assert all(frame["emptyFrame"] is False for frame in route["focusFrames"])
        assert route["fullSequenceGenerated"] is True
        assert route["stage3MechanicalPlaybackGenerated"] is True

    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        stage4.build_c2_full_review(
            output,
            choices=choices,
            authorized=True,
            blender=Path("blender.exe"),
            runner=fake_runner,
        )


def test_step9_rejects_machine_valid_candidate_with_unapproved_final_choice(tmp_path):
    output = tmp_path / "c2-full-review-r1"
    alternate = {
        CHAMBER: {6: "B", 65: "B"},
        CONDENSER: {87: "A", 8: "A"},
    }
    pending = build_pending_c2(stage4, output, alternate)
    stage4.record_c2_browser_evidence(
        output, make_browser_evidence(stage4, pending)
    )

    with pytest.raises(ValueError, match="four approved final selections"):
        stage4.record_stage4_selection_and_close(
            output,
            choices=alternate,
            approved_on="2026-08-31",
            authorized=True,
        )


def test_step9_and_closed_validator_reject_unknown_choice_units(tmp_path):
    copied = tmp_path / "c2-full-review-r1"
    copy_c2_pending_step9_candidate(copied)
    choices = approved_step9_choices()
    choices["unauthorized_extra_unit"] = {1: "A"}
    with pytest.raises(ValueError, match="exactly the approved semantic units"):
        stage4.record_stage4_selection_and_close(
            copied,
            choices=choices,
            approved_on="2026-08-31",
            authorized=True,
        )

    closed = tmp_path / "closed-c2-full-review-r1"
    shutil.copytree(C2_FULL_REVIEW_OUTPUT, closed)
    manifest_path = closed / "c2-full-review-manifest.json"
    report = json.loads(manifest_path.read_text(encoding="utf-8"))
    report["c1HumanChoices"]["unauthorized_extra_unit"] = {"1": "A"}
    manifest_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="exactly the approved semantic units"):
        stage4.validate_c2_full_review(closed)


@pytest.mark.parametrize(
    "mutation",
    ["provenance-swap", "focus-alias", "relative-escape", "absolute-path", "c1-reuse-alias"],
)
def test_c2_validator_rejects_manifest_only_focus_binding_drift(
    tmp_path, mutation
):
    copied = tmp_path / "c2-full-review-r1"
    shutil.copytree(C2_FULL_REVIEW_OUTPUT, copied)
    manifest_path = copied / "c2-full-review-manifest.json"
    report = json.loads(manifest_path.read_text(encoding="utf-8"))
    first = report["routes"][0]["focusFrames"]
    other = report["routes"][1]["focusFrames"]

    if mutation == "provenance-swap":
        first[12]["provenance"], first[1]["provenance"] = (
            first[1]["provenance"],
            first[12]["provenance"],
        )
    elif mutation == "focus-alias":
        first[1]["path"] = other[1]["path"]
        first[1]["sha256"] = other[1]["sha256"]
    elif mutation == "relative-escape":
        original = first[1]["path"]
        first[1]["path"] = f"../{copied.name}/{original}"
    elif mutation == "absolute-path":
        first[1]["path"] = str((copied / first[1]["path"]).resolve())
    else:
        first[0]["path"] = first[12]["path"]
        first[0]["sha256"] = first[12]["sha256"]

    manifest_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="focus binding|provenance"):
        stage4.validate_c2_full_review(copied)


def test_c2_validator_rejects_worker_audit_frame_mapping_drift(tmp_path):
    copied = tmp_path / "c2-full-review-r1"
    copy_c2_pending_browser_candidate(copied)
    manifest_path = copied / "c2-full-review-manifest.json"
    report = json.loads(manifest_path.read_text(encoding="utf-8"))
    audit_path = copied / "worker-audit.json"
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    record = audit["routes"][0]["frames"][0]
    alias = audit["routes"][1]["frames"][0]
    record["path"] = alias["path"]
    record["sha256"] = alias["sha256"]
    audit_path.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    report["inventorySha256"]["worker-audit.json"] = stage4.sha256(audit_path)
    report["reviewAssetInventorySha256"] = stage4.canonical_json_sha256(
        stage4._c2_review_asset_inventory(copied)
    )
    manifest_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    with pytest.raises(ValueError, match="worker.*frame"):
        stage4.validate_c2_full_review(copied)


@pytest.mark.parametrize(
    "mutation", ["empty-orbit", "short-r2-expand", "aliased-r2-close"]
)
def test_c2_validator_rejects_incomplete_local_provenance_mappings(
    tmp_path, mutation
):
    copied = tmp_path / "c2-full-review-r1"
    shutil.copytree(C2_FULL_REVIEW_OUTPUT, copied)
    manifest_path = copied / "c2-full-review-manifest.json"
    report = json.loads(manifest_path.read_text(encoding="utf-8"))
    route = report["routes"][0]
    if mutation == "empty-orbit":
        route["orbitPrefixReviewAssets"] = []
    elif mutation == "short-r2-expand":
        route["stage3R2"]["expandReviewAssets"] = route["stage3R2"][
            "expandReviewAssets"
        ][:-1]
    else:
        route["stage3R2"]["closeReviewAssets"] = list(
            route["stage3R2"]["expandReviewAssets"]
        )
    manifest_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="local provenance mapping"):
        stage4.validate_c2_full_review(copied)


def test_step8_c2_review_page_exposes_full_flow_pause_failure_and_fallback(tmp_path):
    require_step8_integration_assets()
    c1 = stage4.validate_c1_keyframe_precheck(C1_KEYFRAME_OUTPUT)
    stage3 = json.loads(stage4.STAGE3_R2_MANIFEST.read_text(encoding="utf-8"))
    routes = stage4.c2_route_contracts(
        c1,
        stage3,
        {
            CHAMBER: {6: "A", 65: "B"},
            CONDENSER: {87: "A", 8: "A"},
        },
    )
    for route in routes:
        route["focusFrames"] = [
            {
                "sampleIndex": index,
                "path": f"frames/{route['routeId']}/focus-{index:03d}.png",
            }
            for index in range(25)
        ]
        route["orbitPrefixReviewAssets"] = [
            f"review-assets/orbit/frame-{index:03d}.png"
            for index in route["orbitPrefixIndices"]
        ]
        route["stage3R2"]["expandReviewAssets"] = [
            f"review-assets/stage3/{asset}"
            for asset in route["stage3R2"]["expandAssets"]
        ]
        route["stage3R2"]["closeReviewAssets"] = list(
            reversed(route["stage3R2"]["expandReviewAssets"])
        )
        if route["stage3R2"]["inspectionLight"] is not None:
            inspection = route["stage3R2"]["inspectionLight"]
            inspection["unlitReviewAsset"] = (
                f"review-assets/stage3/{inspection['unlitAsset']}"
            )
            inspection["litReviewAsset"] = (
                f"review-assets/stage3/{inspection['litAsset']}"
            )
    path = stage4._write_c2_review_page(
        tmp_path, routes, review_asset_inventory_sha256="A" * 64
    )
    html = path.read_text(encoding="utf-8")

    for token in (
        '<div class="routes">',
        'data-source="model"',
        'data-source="name"',
        'data-action="pause"',
        'data-action="replay"',
        'data-action="static-fallback"',
        "Promise.all",
        "failAsset",
        "prefers-reduced-motion",
        "pauseHeld",
        "resumeSameDirection",
        "resumeFromHeldPoint",
        "resumeExpectation=null",
        "resumeExpectation={label:heldLabel,index:heldIndex+1,asset:heldAssets[heldIndex+1],observed:false}",
        "resumeExpectation.label===label&&resumeExpectation.index===index&&resumeExpectation.asset===currentAsset",
        "resumeExpectation.observed",
        "phaseWaiters=new Set()",
        "function waitForPhaseEntry(phase,token,timeoutMs,label)",
        "phaseWaiters.add(waiter)",
        "phaseWaiters.delete(waiter)",
        "clearTimeout(waiter.timer)",
        "waiter.phase===value&&waiter.token===token",
        "function setPhase(value,token=runToken)",
        "setPhase(phase,token)",
        "setPhase('inspection-fade-in',token)",
        "const expectedOldToken=runToken+1",
        "const phasePromise=waitForPhaseEntry(phase,expectedOldToken,15000",
        "if(oldToken!==expectedOldToken)",
        "await phasePromise",
        "routeCoverage",
        "cancelRun",
        "waitUntil",
        "routeSwitchDuringFocusSafe",
        "fallbackDuringInspectionSafe",
        "boundedWaitFailureObserved",
        "harness-timeout-probe",
        "requestFailures",
        "captureFrameRestored",
        "if(query.has('post'))",
        "fetch('/result'",
    ):
        assert token in html
    assert "waitUntil(()=>currentSequenceIndex!==heldIndex" not in html
    assert "waitUntil(()=>currentPhase===phase" not in html
    assert "phaseVisits" not in html
    assert html.index("const phasePromise=waitForPhaseEntry") < html.index(
        "const oldPromise=playRoute"
    )
    assert html.index("const oldToken=runToken") < html.index("await phasePromise")
    phase_writes = (
        html.replace("currentPhase===", "")
        .replace("currentPhase='idle'", "")
        .replace("currentPhase=value", "")
    )
    assert "currentPhase=" not in phase_writes
    payload_text = html.split('<script id="c2-data" type="application/json">', 1)[1].split(
        "</script>", 1
    )[0]
    payload = json.loads(payload_text)
    assert len(payload) == 8
    for route in payload:
        assert len(route["orbitPrefix"]) > 1
        assert len(route["focus"]) == 25
        assert len(route["expand"]) == 25
        assert len(route["close"]) == 25
        assert route["overviewReturn"] == list(reversed(route["focus"])) + list(
            reversed(route["orbitPrefix"])
        )
        assert route["captureFrame"] == route["orbitPrefix"][0]
        assert route["modelHotspotQualified"] is True


def test_step8_c2_worker_renders_only_non_reused_samples_and_restores_scene():
    source = inspect.getsource(stage4.c2_full_review_worker)
    assert "rendered_indices = [index for index in range(25) if index not in {0, 12, 24}]" in source
    assert "polyline_offset_factors(route[\"curveSamplePositions\"])" in source
    assert 'target.location = Vector(route["commonFields"]["targetSamples"][sample_index])' in source
    assert 'camera.data.lens = route["commonFields"]["lensSamplesMm"][sample_index]' in source
    assert 'f"focus-{sample_index:03d}.png"' in source
    assert '"twinkle-stage4-c2-full-worker-v1"' in source
    assert '"candidateBlendSaved": False' in source
    assert '"temporaryDataBlocksRemaining": temporary_remaining' in source
    module_source = MODULE_PATH.read_text(encoding="utf-8")
    assert '"--stage4-c2-full-worker"' in module_source
    assert "c2_full_review_worker(arguments[worker_index + 1])" in module_source


def test_step8_existing_worker_audit_binds_only_to_exact_curve_contract():
    assert stage4.C2_WORKER_EXPECTED_POSITION_FLOAT32_TOLERANCE_M == 1e-7
    contract = {
        "routeId": "route-A",
        "curveSamplePositions": [[0.0, 0.0, 0.0], [1.0, 2.0, 3.0]],
    }
    worker = {
        "schema": "twinkle-stage4-c2-full-worker-v1",
        "routes": [
            {
                "routeId": "route-A",
                "frames": [
                    {"sampleIndex": 1, "expectedPosition": [1.0, 2.0, 3.0]}
                ],
            }
        ],
    }

    bound = stage4.bind_c2_worker_audit_contract(worker, [contract])

    assert bound["contractSha256"] == stage4.canonical_json_sha256([contract])
    altered = json.loads(json.dumps(contract))
    altered["curveSamplePositions"][1][2] = 4.0
    with pytest.raises(ValueError, match="expected position"):
        stage4.bind_c2_worker_audit_contract(worker, [altered])


def test_step8_c2_browser_evidence_requires_desktop_mobile_and_failure_path():
    success = {
        "passed": True,
        "imagesLoaded": True,
        "pauseHeld": True,
        "resumeSameDirection": True,
        "resumeFromHeldPoint": True,
        "modelEntryCovered": True,
        "nameEntryCovered": True,
        "routeCoverage": C2_ROUTE_IDS,
        "routeSwitchDuringFocusSafe": True,
        "replayDuringFocusSafe": True,
        "fallbackDuringFocusSafe": True,
        "routeSwitchDuringInspectionSafe": True,
        "replayDuringInspectionSafe": True,
        "fallbackDuringInspectionSafe": True,
        "boundedWaitFailureObserved": True,
        "timedOut": False,
        "captureFrameRestored": True,
        "staticFallbackShown": True,
        "failurePathEntered": False,
        "requestFailures": [],
        "consoleErrors": [],
        "consoleWarnings": [],
        "reviewAssetInventorySha256": "A" * 64,
        "reviewPageSha256": "B" * 64,
    }
    evidence = [
        {"scenario": "desktop", "browserId": "chromium", "viewport": [1440, 1000], **success},
        {"scenario": "mobile", "browserId": "chromium", "viewport": [390, 844], **success},
        {
            "scenario": "injected-failure",
            "browserId": "chromium",
            "viewport": [1440, 1000],
            "passed": True,
            "imagesLoaded": False,
            "pauseHeld": False,
            "resumeSameDirection": False,
            "modelEntryCovered": False,
            "nameEntryCovered": False,
            "captureFrameRestored": False,
            "staticFallbackShown": False,
            "failurePathEntered": True,
            "requestFailures": ["/__c2_injected_missing_asset__.png"],
            "consoleErrors": ["expected injected missing asset 404"],
            "consoleWarnings": [],
            "reviewAssetInventorySha256": "A" * 64,
            "reviewPageSha256": "B" * 64,
        },
        {
            "scenario": "bounded-timeout",
            "browserId": "chromium",
            "viewport": [1440, 1000],
            "passed": False,
            "timedOut": True,
            "timeoutPhase": "harness-timeout-probe",
            "durationMs": 20,
            "requestFailures": [],
            "consoleErrors": [],
            "consoleWarnings": [],
            "reviewAssetInventorySha256": "A" * 64,
            "reviewPageSha256": "B" * 64,
        },
    ]

    assert stage4.validate_c2_browser_evidence(evidence) == evidence
    with pytest.raises(ValueError, match="scenarios"):
        stage4.validate_c2_browser_evidence(evidence[:2])
    incomplete = json.loads(json.dumps(evidence))
    incomplete[0]["routeCoverage"] = incomplete[0]["routeCoverage"][:2]
    with pytest.raises(ValueError, match="route coverage"):
        stage4.validate_c2_browser_evidence(incomplete)
    drifted = json.loads(json.dumps(evidence))
    drifted[1]["reviewPageSha256"] = "C" * 64
    with pytest.raises(ValueError, match="review binding"):
        stage4.validate_c2_browser_evidence(drifted)


def test_step8_c2_browser_evidence_record_turns_machine_gate_green_without_asset_drift(
    tmp_path,
):
    copied = tmp_path / "c2-full-review-r1"
    copy_c2_pending_browser_candidate(copied)
    immutable_before = {
        path.relative_to(copied).as_posix(): stage4.sha256(path)
        for path in copied.rglob("*")
        if path.is_file() and path.name != "c2-full-review-manifest.json"
    }
    success = {
        "passed": True,
        "imagesLoaded": True,
        "pauseHeld": True,
        "resumeSameDirection": True,
        "resumeFromHeldPoint": True,
        "modelEntryCovered": True,
        "nameEntryCovered": True,
        "routeCoverage": C2_ROUTE_IDS,
        "routeSwitchDuringFocusSafe": True,
        "replayDuringFocusSafe": True,
        "fallbackDuringFocusSafe": True,
        "routeSwitchDuringInspectionSafe": True,
        "replayDuringInspectionSafe": True,
        "fallbackDuringInspectionSafe": True,
        "boundedWaitFailureObserved": True,
        "timedOut": False,
        "captureFrameRestored": True,
        "staticFallbackShown": True,
        "failurePathEntered": False,
        "requestFailures": [],
        "consoleErrors": [],
        "consoleWarnings": [],
        "reviewAssetInventorySha256": "A" * 64,
        "reviewPageSha256": "B" * 64,
    }
    evidence = [
        {"scenario": "desktop", "browserId": "chromium", "viewport": [1440, 1000], **success},
        {"scenario": "mobile", "browserId": "chromium", "viewport": [390, 844], **success},
        {
            "scenario": "injected-failure",
            "browserId": "chromium",
            "viewport": [1440, 1000],
            "passed": True,
            "imagesLoaded": False,
            "failurePathEntered": True,
            "requestFailures": ["/__c2_injected_missing_asset__.png"],
            "consoleErrors": ["expected injected missing asset 404"],
            "consoleWarnings": [],
            "reviewAssetInventorySha256": "A" * 64,
            "reviewPageSha256": "B" * 64,
        },
        {
            "scenario": "bounded-timeout",
            "browserId": "chromium",
            "viewport": [1440, 1000],
            "passed": False,
            "timedOut": True,
            "timeoutPhase": "harness-timeout-probe",
            "durationMs": 20,
            "requestFailures": [],
            "consoleErrors": [],
            "consoleWarnings": [],
            "reviewAssetInventorySha256": "A" * 64,
            "reviewPageSha256": "B" * 64,
        },
    ]
    pending_report = json.loads(
        (copied / "c2-full-review-manifest.json").read_text(encoding="utf-8")
    )
    for record in evidence:
        record["reviewAssetInventorySha256"] = pending_report[
            "reviewAssetInventorySha256"
        ]
        record["reviewPageSha256"] = pending_report["reviewPageSha256"]

    report = stage4.record_c2_browser_evidence(copied, evidence)

    assert report["browserMachinePassed"] is True
    assert report["machinePassed"] is True
    assert report["humanVisualApproved"] is False
    assert report["authorizesStep9"] is False
    assert len(report["browserEvidence"]) == 4
    immutable_after = {
        path.relative_to(copied).as_posix(): stage4.sha256(path)
        for path in copied.rglob("*")
        if path.is_file()
        and path.name != "c2-full-review-manifest.json"
        and "browser-results" not in path.parts
    }
    assert immutable_after == immutable_before


def test_step8_c2_browser_evidence_rolls_back_when_final_validation_fails(
    tmp_path, monkeypatch
):
    copied = tmp_path / "c2-full-review-r1"
    copy_c2_pending_browser_candidate(copied)
    manifest_path = copied / "c2-full-review-manifest.json"
    manifest_before = manifest_path.read_bytes()
    immutable_before = {
        path.relative_to(copied).as_posix(): stage4.sha256(path)
        for path in copied.rglob("*")
        if path.is_file() and path != manifest_path
    }
    pending = stage4.validate_c2_full_review(copied)
    evidence = make_c2_browser_evidence(pending)
    real_validate = stage4.validate_c2_full_review
    validation_calls = 0

    def fail_final_validation(output_root):
        nonlocal validation_calls
        validation_calls += 1
        if validation_calls == 2:
            published = json.loads(manifest_path.read_text(encoding="utf-8"))
            assert published["browserMachinePassed"] is True
            assert published["machinePassed"] is True
            assert len(published["browserEvidence"]) == 4
            assert (copied / "browser-results").is_dir()
            raise RuntimeError("injected final C2 validation failure")
        return real_validate(output_root)

    monkeypatch.setattr(stage4, "validate_c2_full_review", fail_final_validation)

    with pytest.raises(RuntimeError, match="injected final C2 validation failure"):
        stage4.record_c2_browser_evidence(copied, evidence)

    assert validation_calls == 2
    assert manifest_path.read_bytes() == manifest_before
    assert not (copied / "browser-results").exists()
    assert not list(copied.glob(".browser-results-txn-*"))
    immutable_after = {
        path.relative_to(copied).as_posix(): stage4.sha256(path)
        for path in copied.rglob("*")
        if path.is_file() and path != manifest_path
    }
    assert immutable_after == immutable_before


def test_step8_c2_review_refresh_changes_only_review_html_and_manifest(tmp_path):
    copied = tmp_path / "c2-full-review-r1"
    copy_c2_pending_browser_candidate(copied)
    mutable = {"review/index.html", "c2-full-review-manifest.json"}
    immutable_before = {
        path.relative_to(copied).as_posix(): stage4.sha256(path)
        for path in copied.rglob("*")
        if path.is_file() and path.relative_to(copied).as_posix() not in mutable
    }

    report = stage4.refresh_c2_review(copied)

    immutable_after = {
        path.relative_to(copied).as_posix(): stage4.sha256(path)
        for path in copied.rglob("*")
        if path.is_file() and path.relative_to(copied).as_posix() not in mutable
    }
    assert immutable_after == immutable_before
    assert "if(query.has('post'))" in (copied / "review/index.html").read_text(
        encoding="utf-8"
    )
    assert report["browserMachinePassed"] is False
    assert report["machinePassed"] is False


def test_step8_c2_review_refresh_rolls_back_when_final_validation_fails(
    tmp_path, monkeypatch
):
    copied = tmp_path / "c2-full-review-r1"
    copy_c2_pending_browser_candidate(copied)
    review_path = copied / "review" / "index.html"
    manifest_path = copied / "c2-full-review-manifest.json"

    review_path.write_bytes(
        review_path.read_bytes() + b"\n<!-- stale-refresh-fixture -->\n"
    )
    stale_report = json.loads(manifest_path.read_text(encoding="utf-8"))
    stale_report["reviewPageSha256"] = stage4.sha256(review_path)
    stale_report["inventorySha256"]["review/index.html"] = stage4.sha256(
        review_path
    )
    manifest_path.write_text(
        json.dumps(stale_report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    stage4.validate_c2_full_review(copied)

    review_before = review_path.read_bytes()
    manifest_before = manifest_path.read_bytes()
    mutable = {"review/index.html", "c2-full-review-manifest.json"}
    immutable_before = {
        path.relative_to(copied).as_posix(): stage4.sha256(path)
        for path in copied.rglob("*")
        if path.is_file() and path.relative_to(copied).as_posix() not in mutable
    }
    expected_review_asset_inventory_sha256 = stage4.canonical_json_sha256(
        immutable_before
    )
    real_validate = stage4.validate_c2_full_review
    injected_error = RuntimeError("injected final C2 review validation failure")
    validation_calls = 0

    def fail_final_validation(output_root):
        nonlocal validation_calls
        validation_calls += 1
        if validation_calls == 2:
            published_review = review_path.read_bytes()
            published = json.loads(manifest_path.read_text(encoding="utf-8"))
            published_review_sha256 = stage4.sha256(review_path)
            published_inventory = {
                path.relative_to(copied).as_posix(): stage4.sha256(path)
                for path in copied.rglob("*")
                if path.is_file() and path != manifest_path
            }
            assert published_review != review_before
            assert published["reviewPageSha256"] == published_review_sha256
            assert (
                published["reviewAssetInventorySha256"]
                == expected_review_asset_inventory_sha256
            )
            assert published["inventorySha256"] == published_inventory
            raise injected_error
        return real_validate(output_root)

    monkeypatch.setattr(stage4, "validate_c2_full_review", fail_final_validation)

    with pytest.raises(RuntimeError) as exc_info:
        stage4.refresh_c2_review(copied)

    assert exc_info.value is injected_error
    assert validation_calls == 2
    assert review_path.read_bytes() == review_before
    assert manifest_path.read_bytes() == manifest_before
    immutable_after = {
        path.relative_to(copied).as_posix(): stage4.sha256(path)
        for path in copied.rglob("*")
        if path.is_file() and path.relative_to(copied).as_posix() not in mutable
    }
    assert immutable_after == immutable_before
    assert not list(copied.rglob(".*.txn-*"))


def test_step8_c2_reopens_stale_browser_gate_and_preserves_render_assets(tmp_path):
    copied = tmp_path / "c2-full-review-r1"
    copy_c2_pending_browser_candidate(copied)
    pending = stage4.validate_c2_full_review(copied)
    stage4.record_c2_browser_evidence(copied, make_c2_browser_evidence(pending))
    retained = tmp_path / "superseded-browser-results"
    mutable = {"review/index.html", "c2-full-review-manifest.json"}
    immutable_before = {
        path.relative_to(copied).as_posix(): stage4.sha256(path)
        for path in copied.rglob("*")
        if path.is_file()
        and path.relative_to(copied).as_posix() not in mutable
        and "browser-results" not in path.relative_to(copied).parts
    }

    report = stage4.reopen_c2_browser_gate(
        copied,
        retained_root=retained,
        reason="orbit-prefix-and-eight-route-evidence-gap",
        authorized=True,
    )

    assert retained.is_dir()
    assert sorted(path.name for path in retained.glob("*.json")) == [
        "bounded-timeout.json",
        "desktop.json",
        "injected-failure.json",
        "mobile.json",
        "superseded.json",
    ]
    assert not (copied / "browser-results").exists()
    assert report["browserMachinePassed"] is False
    assert report["browserEvidence"] == []
    assert report["machinePassed"] is False
    assert all(len(route["orbitPrefixIndices"]) > 1 for route in report["routes"])
    immutable_after = {
        path.relative_to(copied).as_posix(): stage4.sha256(path)
        for path in copied.rglob("*")
        if path.is_file()
        and path.relative_to(copied).as_posix() not in mutable
        and "browser-results" not in path.relative_to(copied).parts
    }
    assert immutable_after == immutable_before


def test_step8_c2_reopen_rolls_back_when_final_validation_fails(
    tmp_path, monkeypatch
):
    copied = tmp_path / "c2-full-review-r1"
    copy_c2_pending_browser_candidate(copied)
    manifest_path = copied / "c2-full-review-manifest.json"
    review_path = copied / "review" / "index.html"
    browser_root = copied / "browser-results"
    retained = tmp_path / "superseded-browser-results"

    review_path.write_bytes(
        review_path.read_bytes() + b"\n<!-- stale-reopen-validation-fixture -->\n"
    )
    stale_report = json.loads(manifest_path.read_text(encoding="utf-8"))
    stale_report["reviewPageSha256"] = stage4.sha256(review_path)
    stale_report["inventorySha256"]["review/index.html"] = stage4.sha256(
        review_path
    )
    manifest_path.write_text(
        json.dumps(stale_report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    pending = stage4.validate_c2_full_review(copied)
    stage4.record_c2_browser_evidence(copied, make_c2_browser_evidence(pending))

    manifest_before = manifest_path.read_bytes()
    review_before = review_path.read_bytes()
    browser_directories_before = sorted(
        path.relative_to(browser_root).as_posix()
        for path in browser_root.rglob("*")
        if path.is_dir()
    )
    browser_inventory_before = {
        path.relative_to(browser_root).as_posix(): (
            path.read_bytes(),
            stage4.sha256(path),
        )
        for path in browser_root.rglob("*")
        if path.is_file()
    }
    mutable = {"review/index.html", "c2-full-review-manifest.json"}
    render_assets_before = {
        path.relative_to(copied).as_posix(): stage4.sha256(path)
        for path in copied.rglob("*")
        if path.is_file()
        and path.relative_to(copied).as_posix() not in mutable
        and "browser-results" not in path.relative_to(copied).parts
    }
    real_validate = stage4.validate_c2_full_review
    injected_error = RuntimeError("injected reopen final validation failure")
    validation_calls = 0

    def fail_reopen_validation(output_root):
        nonlocal validation_calls
        validation_calls += 1
        assert Path(output_root).resolve() == copied.resolve()
        assert not browser_root.exists()
        published = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert published["browserMachinePassed"] is False
        assert published["browserEvidence"] == []
        assert published["machinePassed"] is False
        assert manifest_path.read_bytes() != manifest_before
        assert review_path.read_bytes() != review_before
        assert b"stale-reopen-validation-fixture" not in review_path.read_bytes()
        rollback_roots = list(copied.parent.glob(".browser-results-reopen-*"))
        assert len(rollback_roots) == 1
        assert sorted(path.name for path in rollback_roots[0].glob("*.json")) == [
            "bounded-timeout.json",
            "desktop.json",
            "injected-failure.json",
            "mobile.json",
            "superseded.json",
        ]
        raise injected_error

    monkeypatch.setattr(stage4, "validate_c2_full_review", fail_reopen_validation)

    with pytest.raises(RuntimeError) as exc_info:
        stage4.reopen_c2_browser_gate(
            copied,
            retained_root=retained,
            reason="injected-final-validation-failure",
            authorized=True,
        )

    assert exc_info.value is injected_error
    assert validation_calls == 1
    assert manifest_path.read_bytes() == manifest_before
    assert review_path.read_bytes() == review_before
    assert browser_root.is_dir()
    assert sorted(
        path.relative_to(browser_root).as_posix()
        for path in browser_root.rglob("*")
        if path.is_dir()
    ) == browser_directories_before
    assert {
        path.relative_to(browser_root).as_posix(): (
            path.read_bytes(),
            stage4.sha256(path),
        )
        for path in browser_root.rglob("*")
        if path.is_file()
    } == browser_inventory_before
    assert not retained.exists()
    assert not list(copied.parent.glob(".browser-results-reopen-*"))
    assert not list(copied.rglob(".*.txn-*"))
    assert {
        path.relative_to(copied).as_posix(): stage4.sha256(path)
        for path in copied.rglob("*")
        if path.is_file()
        and path.relative_to(copied).as_posix() not in mutable
        and "browser-results" not in path.relative_to(copied).parts
    } == render_assets_before


def test_step9_records_approved_routes_replaces_focus_stub_and_closes_stage4(
    tmp_path,
):
    copied = tmp_path / "c2-full-review-r1"
    copy_c2_pending_step9_candidate(copied)
    manifest_path = copied / "c2-full-review-manifest.json"
    immutable_before = {
        path.relative_to(copied).as_posix(): stage4.sha256(path)
        for path in copied.rglob("*")
        if path.is_file() and path != manifest_path
    }

    report = stage4.record_stage4_selection_and_close(
        copied,
        choices=approved_step9_choices(),
        approved_on="2026-08-31",
        authorized=True,
    )

    assert report["routeByUnit"] == {
        CHAMBER: [
            {
                "entryFrame": 6,
                "variant": "A",
                "routeId": f"{CHAMBER}--entry-006--A",
            },
            {
                "entryFrame": 65,
                "variant": "B",
                "routeId": f"{CHAMBER}--entry-065--B",
            },
        ],
        CONDENSER: [
            {
                "entryFrame": 87,
                "variant": "A",
                "routeId": f"{CONDENSER}--entry-087--A",
            },
            {
                "entryFrame": 8,
                "variant": "A",
                "routeId": f"{CONDENSER}--entry-008--A",
            },
        ],
    }
    assert report["entryFrameSet"] == {
        CHAMBER: [6, 65],
        CONDENSER: [87, 8],
    }
    assert report["focusRouteGenerated"] is True
    assert report["humanVisualApproved"] is True
    assert report["authorizesStep9"] is True
    assert report["stage4Closed"] is True
    assert report["authorizesStage5"] is False
    assert report["stage4Closure"] == {
        "approvedBy": "user",
        "approvedOn": "2026-08-31",
        "scope": "stage4-step9-selection-record-and-closure-only",
        "replacesFocusRouteStub": True,
        "authorizesStage5": False,
    }
    immutable_after = {
        path.relative_to(copied).as_posix(): stage4.sha256(path)
        for path in copied.rglob("*")
        if path.is_file() and path != manifest_path
    }
    assert immutable_after == immutable_before


def test_step9_refuses_unapproved_or_drifted_choices_without_writing(tmp_path):
    copied = tmp_path / "c2-full-review-r1"
    copy_c2_pending_step9_candidate(copied)
    manifest_path = copied / "c2-full-review-manifest.json"
    manifest_before = manifest_path.read_bytes()

    with pytest.raises(ValueError, match="explicit step 9 authorization"):
        stage4.record_stage4_selection_and_close(
            copied,
            choices=approved_step9_choices(),
            approved_on="2026-08-31",
            authorized=False,
        )
    drifted = approved_step9_choices()
    drifted[CHAMBER][65] = "A"
    with pytest.raises(ValueError, match="four approved final selections"):
        stage4.record_stage4_selection_and_close(
            copied,
            choices=drifted,
            approved_on="2026-08-31",
            authorized=True,
        )

    assert manifest_path.read_bytes() == manifest_before


def test_step9_rolls_back_manifest_when_final_validation_fails(
    tmp_path, monkeypatch
):
    copied = tmp_path / "c2-full-review-r1"
    copy_c2_pending_step9_candidate(copied)
    manifest_path = copied / "c2-full-review-manifest.json"
    manifest_before = manifest_path.read_bytes()
    real_validate = stage4.validate_c2_full_review
    validation_calls = 0

    def fail_final_validation(output_root):
        nonlocal validation_calls
        validation_calls += 1
        if validation_calls == 2:
            published = json.loads(manifest_path.read_text(encoding="utf-8"))
            assert published["stage4Closed"] is True
            raise RuntimeError("injected final stage 4 closure failure")
        return real_validate(output_root)

    monkeypatch.setattr(stage4, "validate_c2_full_review", fail_final_validation)

    with pytest.raises(RuntimeError, match="injected final stage 4 closure failure"):
        stage4.record_stage4_selection_and_close(
            copied,
            choices=approved_step9_choices(),
            approved_on="2026-08-31",
            authorized=True,
        )

    assert validation_calls == 2
    assert manifest_path.read_bytes() == manifest_before
    assert not list(copied.glob(".c2-full-review-manifest.json.txn-*"))


def test_step9_formal_c2_candidate_is_closed_and_stage5_remains_unauthorized():
    require_step8_integration_assets(include_c2=True)

    report = stage4.validate_c2_full_review(C2_FULL_REVIEW_OUTPUT)

    assert report["stage4Closed"] is True
    assert report["humanVisualApproved"] is True
    assert report["focusRouteGenerated"] is True
    assert report["entryFrameSet"] == {
        CHAMBER: [6, 65],
        CONDENSER: [87, 8],
    }
    assert report["authorizesStage5"] is False


def test_step8_c2_reopen_rolls_back_when_retained_rename_fails(
    tmp_path, monkeypatch
):
    copied = tmp_path / "c2-full-review-r1"
    copy_c2_pending_browser_candidate(copied)
    manifest_path = copied / "c2-full-review-manifest.json"
    review_path = copied / "review" / "index.html"
    browser_root = copied / "browser-results"
    retained = tmp_path / "superseded-browser-results"

    review_path.write_bytes(
        review_path.read_bytes() + b"\n<!-- stale-reopen-rename-fixture -->\n"
    )
    stale_report = json.loads(manifest_path.read_text(encoding="utf-8"))
    stale_report["reviewPageSha256"] = stage4.sha256(review_path)
    stale_report["inventorySha256"]["review/index.html"] = stage4.sha256(
        review_path
    )
    manifest_path.write_text(
        json.dumps(stale_report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    pending = stage4.validate_c2_full_review(copied)
    stage4.record_c2_browser_evidence(copied, make_c2_browser_evidence(pending))

    manifest_before = manifest_path.read_bytes()
    review_before = review_path.read_bytes()
    browser_directories_before = sorted(
        path.relative_to(browser_root).as_posix()
        for path in browser_root.rglob("*")
        if path.is_dir()
    )
    browser_inventory_before = {
        path.relative_to(browser_root).as_posix(): (
            path.read_bytes(),
            stage4.sha256(path),
        )
        for path in browser_root.rglob("*")
        if path.is_file()
    }
    mutable = {"review/index.html", "c2-full-review-manifest.json"}
    render_assets_before = {
        path.relative_to(copied).as_posix(): stage4.sha256(path)
        for path in copied.rglob("*")
        if path.is_file()
        and path.relative_to(copied).as_posix() not in mutable
        and "browser-results" not in path.relative_to(copied).parts
    }
    real_validate = stage4.validate_c2_full_review
    real_rename = Path.rename
    injected_error = OSError("injected retained evidence rename failure")
    validation_calls = 0
    rename_calls = []

    def track_final_validation(output_root):
        nonlocal validation_calls
        validation_calls += 1
        return real_validate(output_root)

    def fail_retained_rename(source, target):
        source_resolved = Path(source).resolve()
        target_resolved = Path(target).resolve()
        if source_resolved == browser_root.resolve():
            assert target_resolved.parent == copied.parent.resolve()
            assert target_resolved.name.startswith(".browser-results-reopen-")
            rename_calls.append("browser-to-rollback")
            return real_rename(source, target)
        if (
            source_resolved.parent == copied.parent.resolve()
            and source_resolved.name.startswith(".browser-results-reopen-")
            and target_resolved == retained.resolve()
        ):
            rename_calls.append("rollback-to-retained")
            assert validation_calls == 1
            assert source_resolved.is_dir()
            assert not browser_root.exists()
            published = json.loads(manifest_path.read_text(encoding="utf-8"))
            assert published["browserMachinePassed"] is False
            assert published["browserEvidence"] == []
            assert published["machinePassed"] is False
            assert manifest_path.read_bytes() != manifest_before
            assert review_path.read_bytes() != review_before
            assert b"stale-reopen-rename-fixture" not in review_path.read_bytes()
            raise injected_error
        if (
            source_resolved.parent == copied.parent.resolve()
            and source_resolved.name.startswith(".browser-results-reopen-")
            and target_resolved == browser_root.resolve()
        ):
            rename_calls.append("rollback-to-browser")
            return real_rename(source, target)
        raise AssertionError(f"unexpected Path.rename call: {source} -> {target}")

    monkeypatch.setattr(stage4, "validate_c2_full_review", track_final_validation)
    monkeypatch.setattr(Path, "rename", fail_retained_rename)

    with pytest.raises(OSError) as exc_info:
        stage4.reopen_c2_browser_gate(
            copied,
            retained_root=retained,
            reason="injected-retained-rename-failure",
            authorized=True,
        )

    assert exc_info.value is injected_error
    assert validation_calls == 1
    assert rename_calls == [
        "browser-to-rollback",
        "rollback-to-retained",
        "rollback-to-browser",
    ]
    assert manifest_path.read_bytes() == manifest_before
    assert review_path.read_bytes() == review_before
    assert browser_root.is_dir()
    assert sorted(
        path.relative_to(browser_root).as_posix()
        for path in browser_root.rglob("*")
        if path.is_dir()
    ) == browser_directories_before
    assert {
        path.relative_to(browser_root).as_posix(): (
            path.read_bytes(),
            stage4.sha256(path),
        )
        for path in browser_root.rglob("*")
        if path.is_file()
    } == browser_inventory_before
    assert not retained.exists()
    assert not list(copied.parent.glob(".browser-results-reopen-*"))
    assert not list(copied.rglob(".*.txn-*"))
    assert {
        path.relative_to(copied).as_posix(): stage4.sha256(path)
        for path in copied.rglob("*")
        if path.is_file()
        and path.relative_to(copied).as_posix() not in mutable
        and "browser-results" not in path.relative_to(copied).parts
    } == render_assets_before
