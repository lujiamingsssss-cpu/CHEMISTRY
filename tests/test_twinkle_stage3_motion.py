import ast
import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image, ImageDraw

import scripts.build_twinkle_stage3_motion as stage3
from tests.twinkle_stage1_3_fixtures import make_stage3_evidence


ROOT = Path(__file__).resolve().parents[1]
CHAMBER = "dual_channel_collection_optics_chamber"
CONDENSER = "dual_channel_condenser_lens_assembly"


@pytest.fixture(scope="module")
def stage3_evidence_base(tmp_path_factory):
    return make_stage3_evidence(tmp_path_factory.mktemp("twinkle-stage3"), stage3)


@pytest.fixture
def stage3_evidence(stage3_evidence_base, monkeypatch):
    for name, value in stage3_evidence_base.patches.items():
        monkeypatch.setattr(stage3, name, value)
    return stage3_evidence_base


def test_authority_and_semantic_contract_is_exact():
    assert stage3.SCHEMA == "twinkle-stage3-dual-hotspot-motion-v1"
    assert stage3.AUTHORITY_MANIFEST == (
        ROOT
        / "output"
        / "twinkle-route1-camera-board-r1-1"
        / "camera-board-manifest.json"
    )
    assert stage3.EXPECTED_AUTHORITY_SHA256 == (
        "8DB0B2055838FA69C6381719587A99A2B132FE526F40EA6F0C231264AD908378"
    )
    assert stage3.EXPECTED_SOURCE_BLEND_SHA256 == (
        "5458C6A3033DF6D1CFD3CAD4B11F3A7DF69BB278D3EE7853767B96E412E7AF81"
    )
    assert stage3.EXPECTED_CANDIDATE_BLEND_SHA256 == (
        "584EBB7F8F5F5CAEB7AF469DBF02A465DE7016D67A9D64539A018E9F6DDD4FD6"
    )
    assert stage3.SEMANTIC_UNITS == (CHAMBER, CONDENSER)


def test_state_controls_and_stage4_segments_are_frozen():
    assert stage3.TOP_LEVEL_STATES == ("global", "action", "explanation")
    assert stage3.STAGE4_SEGMENTS == {
        "focus": {"kind": "stub", "pausable": True},
        "overviewReturn": {"kind": "stub", "pausable": True},
    }
    assert stage3.CONTROL_MATRIX == {
        "global": {
            "modelHotspots": {"visible": True, "enabled": True},
            "unitNames": {"visible": True, "enabled": True},
            "globalToggle": {"visible": True, "enabled": True},
            "actionToggle": {
                "visible": True,
                "enabled": False,
                "label": "暂停动作",
            },
            "return": {"visible": True, "enabled": False},
        },
        "action": {
            "modelHotspots": {"visible": False, "enabled": False},
            "unitNames": {"visible": True, "enabled": False},
            "globalToggle": {"visible": True, "enabled": False},
            "actionToggle": {"visible": True, "enabled": True},
            "return": {"visible": True, "enabled": False},
        },
        "explanation": {
            "modelHotspots": {"visible": False, "enabled": False},
            "unitNames": {"visible": True, "enabled": False},
            "globalToggle": {"visible": True, "enabled": False},
            "actionToggle": {
                "visible": True,
                "enabled": False,
                "label": "暂停动作",
            },
            "return": {"visible": True, "enabled": True},
        },
    }


def test_format_experiment_matrix_and_single_candidate_are_bounded():
    assert stage3.FORMAT_EXPERIMENT == {
        "resolution": (1280, 900),
        "fps": 24,
        "codec": "libx264",
        "preset": "slow",
        "profile": "high",
        "crf": 10,
        "pixelFormat": "yuv420p",
        "color": "bt709",
        "faststart": True,
        "allFramesSeekable": True,
        "audio": False,
    }
    assert stage3.BROWSER_MATRIX == (
        {"id": "chrome-151", "major": 151, "support": "required"},
        {"id": "chrome-for-testing-150", "major": 150, "support": "required"},
        {"id": "edge-151", "major": 151, "support": "required"},
        {"id": "edge-150", "major": 150, "support": "not-tested"},
    )
    assert stage3.FALLBACK_FORMAT == "lossless-png-sequence"


def test_authority_hash_and_manifest_semantics_validate(stage3_evidence):
    manifest = stage3.validate_authority()
    assert set(manifest["units"]) == {CHAMBER, CONDENSER}


@pytest.mark.parametrize(
    ("changes", "error"),
    [
        (
            {"authorityManifest": "experiment-manifest.json"},
            "authority manifest",
        ),
        (
            {"semanticUnits": ["j_green_filter_subassembly", CONDENSER]},
            "semantic units",
        ),
        (
            {"semanticUnits": [CHAMBER, "f_dual_acl_housing"]},
            "semantic units",
        ),
        (
            {"payloadTerms": ["green-filter", "red-filter"]},
            "forbidden legacy term",
        ),
        ({"writeProductionPage": True}, "production page"),
    ],
)
def test_request_validation_rejects_retired_contracts(tmp_path, changes, error):
    request = stage3.default_request(tmp_path / "new-output")
    request.update(changes)
    with pytest.raises(ValueError, match=error):
        stage3.validate_request(request)


def test_request_validation_rejects_existing_output(tmp_path):
    output_root = tmp_path / "existing"
    output_root.mkdir()
    request = stage3.default_request(output_root)
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        stage3.validate_request(request)


@pytest.mark.parametrize(
    ("top_level", "global_orbit", "action_playback", "global_label", "action_label"),
    [
        ("global", "running", None, "暂停展示", "暂停动作"),
        ("global", "paused", None, "开始展示", "暂停动作"),
        ("action", "paused", "running", "开始展示", "暂停动作"),
        ("action", "paused", "paused", "开始展示", "继续动作"),
        ("explanation", "paused", None, "开始展示", "暂停动作"),
    ],
)
def test_controls_keep_layout_and_dynamic_labels(
    top_level, global_orbit, action_playback, global_label, action_label
):
    snapshot = stage3.state(
        top_level,
        globalOrbit=global_orbit,
        actionPlayback=action_playback,
    )
    controls = stage3.controls_for(snapshot)
    assert all(
        controls[name]["visible"]
        for name in ("unitNames", "globalToggle", "actionToggle", "return")
    )
    assert controls["modelHotspots"]["visible"] is (top_level == "global")
    assert controls["globalToggle"]["label"] == global_label
    assert controls["actionToggle"]["label"] == action_label


def test_pause_and_resume_preserve_progress_and_direction():
    snapshot = stage3.state(
        "action",
        actionPhase="expand",
        actionPlayback="running",
        progress=0.5,
        direction="forward",
    )
    paused = stage3.reduce_state(
        snapshot, {"type": "control", "control": "actionToggle"}
    )
    assert paused["actionPlayback"] == "paused"
    assert paused["progress"] == 0.5
    assert paused["direction"] == "forward"

    resumed = stage3.reduce_state(
        paused, {"type": "control", "control": "actionToggle"}
    )
    assert resumed["actionPlayback"] == "running"
    assert resumed["progress"] == 0.5
    assert resumed["direction"] == "forward"


@pytest.mark.parametrize(
    ("snapshot", "control"),
    [
        (stage3.state("action", actionPhase="expand"), "globalToggle"),
        (stage3.state("action", actionPhase="expand"), "unitNames"),
        (stage3.state("explanation"), "actionToggle"),
        (stage3.state("global"), "return"),
    ],
)
def test_disabled_controls_are_no_ops(snapshot, control):
    assert stage3.reduce_state(
        snapshot, {"type": "control", "control": control}
    ) == snapshot


def test_chamber_trajectory_holds_inspection_light_until_detail_exit():
    snapshot = stage3.state("global", globalOrbit="running")
    snapshot = stage3.reduce_state(
        snapshot, {"type": "select", "unit": CHAMBER}
    )
    assert (snapshot["topLevel"], snapshot["actionPhase"]) == ("action", "focus")

    snapshot = stage3.reduce_state(snapshot, {"type": "segmentComplete"})
    assert snapshot["actionPhase"] == "expand"
    snapshot = stage3.reduce_state(snapshot, {"type": "progress", "value": 1.0})
    snapshot = stage3.reduce_state(snapshot, {"type": "segmentComplete"})
    assert snapshot["inspectionLight"] == "entering"

    snapshot = stage3.reduce_state(snapshot, {"type": "inspectionEnterComplete"})
    assert snapshot["topLevel"] == "explanation"
    assert snapshot["inspectionLight"] == "stable"
    snapshot = stage3.reduce_state(
        snapshot, {"type": "control", "control": "return"}
    )
    assert snapshot["awaitingDetailExit"] is True
    assert snapshot["inspectionLight"] == "stable"

    snapshot = stage3.reduce_state(snapshot, {"type": "detailExited"})
    assert (snapshot["topLevel"], snapshot["actionPhase"]) == ("action", "close")
    assert snapshot["inspectionLight"] == "exiting"
    snapshot = stage3.reduce_state(snapshot, {"type": "inspectionExitComplete"})
    assert snapshot["inspectionLight"] == "off"
    snapshot = stage3.reduce_state(snapshot, {"type": "progress", "value": 0.0})
    snapshot = stage3.reduce_state(snapshot, {"type": "segmentComplete"})
    assert snapshot["actionPhase"] == "overviewReturn"
    snapshot = stage3.reduce_state(snapshot, {"type": "segmentComplete"})
    assert snapshot["topLevel"] == "global"
    assert snapshot["globalOrbit"] == "paused"


def test_condenser_trajectory_has_no_inspection_light():
    snapshot = stage3.state("global")
    snapshot = stage3.reduce_state(
        snapshot, {"type": "select", "unit": CONDENSER}
    )
    snapshot = stage3.reduce_state(snapshot, {"type": "segmentComplete"})
    snapshot = stage3.reduce_state(snapshot, {"type": "progress", "value": 1.0})
    snapshot = stage3.reduce_state(snapshot, {"type": "segmentComplete"})
    assert snapshot["topLevel"] == "explanation"
    assert snapshot["inspectionLight"] == "off"


@pytest.mark.parametrize("reason", ["reduced-motion", "media-load-failed"])
def test_reduced_motion_and_load_failure_use_static_png_fallback(reason):
    snapshot = stage3.state("global")
    snapshot = stage3.reduce_state(
        snapshot, {"type": "select", "unit": CHAMBER, "fallbackReason": reason}
    )
    assert snapshot["topLevel"] == "action"
    assert snapshot["actionPhase"] == "expand"
    assert snapshot["playbackMode"] == "static-fade"
    assert snapshot["assetFormat"] == "lossless-png-sequence"
    assert snapshot["fallbackReason"] == reason


def test_format_experiment_machine_contract_is_complete_and_awaits_human(stage3_evidence):
    report = stage3.validate_format_experiment(stage3_evidence.format_root)
    assert report["schema"] == "twinkle-stage3-format-experiment-v1"
    assert report["candidate"]["parameterSetCount"] == 1
    assert report["browserMatrix"] == {
        "chrome-151": "validation-failed",
        "chrome-for-testing-150": "not-run-after-video-route-failure",
        "edge-151": "not-run-after-video-route-failure",
        "edge-150": "not-tested",
    }
    assert report["machinePassed"] is False
    assert report["videoRouteFailed"] is True
    assert report["humanDetailApproved"] is True
    assert report["selectedFormat"] == "lossless-png-sequence"
    assert report["humanApproval"] == {
        "approvedFormat": "lossless-png-sequence",
        "approvedBy": "user",
        "approvedOn": "2026-08-26",
        "scope": "stage3-step3-format-only",
        "authorizesStep4": False,
    }


def test_any_required_browser_evidence_failure_irreversibly_selects_png():
    decision = stage3.format_decision(
        {
            "chrome-151": "validation-failed",
            "chrome-for-testing-150": "not-run-after-video-route-failure",
            "edge-151": "not-run-after-video-route-failure",
            "edge-150": "not-tested",
        }
    )
    assert decision == {
        "browserMatrix": {
            "chrome-151": "validation-failed",
            "chrome-for-testing-150": "not-run-after-video-route-failure",
            "edge-151": "not-run-after-video-route-failure",
            "edge-150": "not-tested",
        },
        "videoRouteFailed": True,
        "machinePassed": False,
        "selectedFormat": "lossless-png-sequence",
    }


def test_encode_command_writes_bt709_into_frames_and_x264_vui():
    command = stage3.format_encode_command("ffmpeg", "frames.txt", "candidate.mp4")
    assert command[command.index("-vf") + 1] == (
        "setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709"
    )
    assert command[command.index("-x264-params") + 1] == (
        "colorprim=bt709:transfer=bt709:colormatrix=bt709"
    )
    assert command[command.index("-crf") + 1] == "10"
    assert command[command.index("-preset") + 1] == "slow"


def test_browser_harness_waits_for_presented_frame_after_seek():
    harness = stage3._browser_harness_html([[0, 0, 0]] * 3)
    assert "requestVideoFrameCallback" in harness
    assert "await presentedFrame()" in harness
    assert "presentedFrame timeout" in harness
    assert "video.currentTime >= value+0.05" in harness


def test_chamber_lowres_candidate_machine_contract_records_human_approval(stage3_evidence):
    report = stage3.validate_chamber_lowres_candidate(stage3_evidence.chamber_root)
    assert report["schema"] == "twinkle-stage3-chamber-lowres-v1"
    assert report["unit"] == CHAMBER
    assert report["selectedFormat"] == "lossless-png-sequence"
    assert report["render"] == {
        "resolution": [640, 450],
        "samples": 64,
        "fps": 24,
        "durationMs": 1000,
        "frameCount": 25,
    }
    assert report["timingMs"] == {"seam": 240, "acceleratedTravel": 760}
    assert report["motion"]["frameIndices"] == list(range(25))
    assert report["motion"]["closeFrameIndices"] == list(reversed(range(25)))
    assert report["motion"]["progress"][0] == 0.0
    assert report["motion"]["progress"][-1] == 1.0
    assert report["motion"]["progress"] == sorted(
        set(report["motion"]["progress"])
    )
    assert report["motion"]["seamProgress"] == 0.06
    assert report["motion"]["bothPanelsSynchronous"] is True
    for frame, progress in zip(report["frames"], report["motion"]["progress"]):
        offsets = frame["componentOffsetsM"]
        assert offsets["bottomCover"] == pytest.approx(
            [0.0, 0.0, -0.14 * progress], abs=1e-7
        )
        assert offsets["sidePanel"] == pytest.approx(
            [0.0, -0.1 * progress, 0.0], abs=1e-7
        )
        assert set(frame["rootWorldMatrices"]) == {
            "DetectBox_Bottom_Mala2020:1",
            "Side2_optics:1",
        }
    assert report["pauseEvidence"] == [
        {
            "percent": 25,
            "frameIndex": 6,
            "holdUsesSameFrame": True,
            "resumeFrameIndex": 7,
            "direction": "forward",
        },
        {
            "percent": 50,
            "frameIndex": 12,
            "holdUsesSameFrame": True,
            "resumeFrameIndex": 13,
            "direction": "forward",
        },
        {
            "percent": 75,
            "frameIndex": 18,
            "holdUsesSameFrame": True,
            "resumeFrameIndex": 19,
            "direction": "forward",
        },
    ]
    assert report["inspectionLight"]["transitionMs"] == {
        "enter": 900,
        "hold": 500,
        "exit": 700,
    }
    assert report["inspectionLight"]["handoff"] == (
        "exit-complete-before-close-frame-23"
    )
    assert report["endpointReferences"]["closed"]["sha256"] == (
        stage3_evidence.endpoint_sha256["chamber_closed"]
    )
    assert report["endpointReferences"]["open"]["sha256"] == (
        stage3_evidence.endpoint_sha256["chamber_open"]
    )
    assert report["endpointReferences"]["inspectionLit"]["sha256"] == (
        stage3_evidence.endpoint_sha256["chamber_inspection"]
    )
    assert report["quality"]["blackFrameCount"] == 0
    assert report["quality"]["duplicateAdjacentFrameCount"] == 0
    assert report["quality"]["endpointPixelMaeVsStage1HalfSize"] <= 1.0
    assert report["machinePassed"] is True
    assert report["humanVisualApproved"] is True
    assert report["humanApproval"] == {
        "approvedUnit": CHAMBER,
        "approvedBy": "user",
        "approvedOn": "2026-08-26",
        "scope": "stage3-step4-chamber-lowres-only",
        "authorizesStep5": False,
    }
    assert report["authorizesStep5"] is False


def test_blender_worker_entry_does_not_import_pillow_at_module_top_level():
    source_path = ROOT / "scripts" / "build_twinkle_stage3_motion.py"
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert not any(
        isinstance(node, ast.ImportFrom) and node.module == "PIL"
        for node in tree.body
    )
    assert '"--stage3-condenser-worker" not in sys.argv' in source


def test_chamber_blender_command_makes_python_exceptions_nonzero():
    command = stage3.chamber_blender_command(
        "blender.exe", "candidate.blend", "staging"
    )
    python_index = command.index("--python")
    assert command[python_index - 2 : python_index] == [
        "--python-exit-code",
        "1",
    ]


def test_chamber_review_page_resolves_assets_from_its_review_subdirectory(stage3_evidence):
    html = (stage3_evidence.chamber_root / "review" / "index.html").read_text(
        encoding="utf-8"
    )
    assert '"../frames/frame-000.png"' in html
    assert '"../inspection/enter-000.png"' in html
    assert '"../inspection/stable.png"' in html


def test_condenser_lowres_candidate_machine_contract_is_complete_and_awaits_human(stage3_evidence):
    report = stage3.validate_condenser_lowres_candidate(stage3_evidence.condenser_root)
    assert report["schema"] == "twinkle-stage3-condenser-lowres-v1"
    assert report["unit"] == CONDENSER
    assert report["selectedFormat"] == "lossless-png-sequence"
    assert report["render"] == {
        "resolution": [640, 450],
        "samples": 64,
        "fps": 24,
        "durationMs": 1000,
        "frameCount": 25,
    }
    assert report["motion"]["frameIndices"] == list(range(25))
    assert report["motion"]["closeFrameIndices"] == list(reversed(range(25)))
    assert report["motion"]["progress"] == sorted(
        set(report["motion"]["progress"])
    )
    assert report["motion"]["progress"][0] == 0.0
    assert report["motion"]["progress"][-1] == 1.0
    for frame, progress in zip(report["frames"], report["motion"]["progress"]):
        assert frame["componentOffsetsM"]["condenserAssembly"] == pytest.approx(
            [0.034 * progress, 0.012 * progress, -0.016 * progress], abs=1e-7
        )
        assert set(frame["rootWorldMatrices"]) == {
            "SHOWCASE_GROUP__f_dual_acl_housing"
        }
    assert report["pauseEvidence"] == [
        {
            "percent": 25,
            "frameIndex": 6,
            "holdUsesSameFrame": True,
            "resumeFrameIndex": 7,
            "direction": "forward",
        },
        {
            "percent": 50,
            "frameIndex": 12,
            "holdUsesSameFrame": True,
            "resumeFrameIndex": 13,
            "direction": "forward",
        },
        {
            "percent": 75,
            "frameIndex": 18,
            "holdUsesSameFrame": True,
            "resumeFrameIndex": 19,
            "direction": "forward",
        },
    ]
    assert report["inspectionLight"] is None
    assert report["cleanup"]["method"] == "ffmpeg-removelogo-bitmap-mask"
    assert report["cleanup"]["cleanedFrameCount"] == 23
    assert report["cleanup"]["outsideMaskChangedPixels"] == 0
    assert report["cleanup"]["boundsMonotonic"] is True
    assert report["endpointReferences"]["closed"]["sha256"] == (
        stage3_evidence.endpoint_sha256["condenser_closed"]
    )
    assert report["endpointReferences"]["open"]["sha256"] == (
        stage3_evidence.endpoint_sha256["condenser_open"]
    )
    assert report["styleReference"] == {
        "unit": CHAMBER,
        "manifest": (
            "output/.twinkle-stage3-chamber-lowres-20260826/"
            "chamber-lowres-r1/chamber-lowres-manifest.json"
        ),
        "humanVisualApproved": True,
    }
    assert report["quality"]["blackFrameCount"] == 0
    assert report["quality"]["duplicateAdjacentFrameCount"] == 0
    assert report["quality"]["endpointPixelMaeVsStage1HalfSize"] <= 1.0
    assert report["machinePassed"] is True
    assert report["humanVisualApproved"] is False
    assert report["authorizesStep6"] is False


def test_condenser_blender_command_preserves_python_exception_exit_gate():
    command = stage3.condenser_blender_command(
        "blender.exe", "candidate.blend", "staging"
    )
    python_index = command.index("--python")
    assert command[python_index - 2 : python_index] == [
        "--python-exit-code",
        "1",
    ]


def test_condenser_unique_repair_contract_is_model_native_and_bounded():
    contract = stage3.condenser_repair_contract()
    assert contract["attempt"] == 1
    assert contract["rootCause"] == {
        "object": "ACL25416U_MOUNT_Red2 :: 实体1",
        "classification": "cad-triangulated-geometry-and-surface-normals",
        "removelogoCause": False,
        "uvOrNormalTextureCause": False,
    }
    assert contract["modelCleanup"] == {
        "method": "temporary-mesh-limited-dissolve",
        "object": "ACL25416U_MOUNT_Red2 :: 实体1",
        "sourceMeshPreserved": True,
    }
    assert contract["occlusion"] == {
        "method": "reuse-cad-occluder-group-follow-root",
        "group": "OCCLUDER_GROUP__f_dual_acl_housing",
        "meshes": ["FrontCover :: 实体1", "Side1 :: 实体1"],
        "syntheticMeshesCreated": 0,
    }
    assert contract["animation"] == {
        "method": "native-fcurve",
        "frameRange": [0, 24],
        "keyframesPerLocationChannel": 25,
        "interpolation": "BEZIER",
        "handleType": "AUTO_CLAMPED",
    }
    assert contract["postprocess"] == {
        "method": "none",
        "removelogoApplied": False,
    }


def test_condenser_repair_blender_command_keeps_exception_gate_and_worker_scope():
    command = stage3.condenser_repair_blender_command(
        "blender.exe", "candidate.blend", "staging"
    )
    python_index = command.index("--python")
    assert command[python_index - 2 : python_index] == [
        "--python-exit-code",
        "1",
    ]
    assert command[-2:] == ["--stage3-condenser-repair-worker", "staging"]


def test_condenser_unique_repair_candidate_uses_model_cleanup_occlusion_and_fcurves(
    tmp_path, monkeypatch
):
    output = tmp_path / "condenser-lowres-r2"
    frames_root = output / "frames"
    frames_root.mkdir(parents=True)
    full_offset = [0.034, 0.012, -0.016]
    monkeypatch.setattr(
        stage3,
        "validate_authority",
        lambda: {
            "units": {
                CONDENSER: {
                    "fullOffsetsM": {"condenserAssembly": full_offset}
                }
            }
        },
    )
    frames = []
    progress_values = [stage3.condenser_motion_progress(index) for index in range(25)]
    for index, progress in enumerate(progress_values):
        path = frames_root / f"frame-{index:03d}.png"
        Image.new("RGB", (640, 450), (index, index, index)).save(path)
        frames.append(
            {
                "index": index,
                "progress": progress,
                "path": f"frames/{path.name}",
                "sha256": stage3.sha256(path),
                "componentOffsetsM": {
                    "condenserAssembly": [value * progress for value in full_offset]
                },
                "rootWorldMatrices": {
                    "SHOWCASE_GROUP__f_dual_acl_housing": []
                },
            }
        )
    for relative in stage3.CONDENSER_LOWRES_REVIEW_FILES:
        path = output / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix == ".png":
            Image.new("RGB", (1, 1), "white").save(path)
        else:
            path.write_text("{}", encoding="utf-8")
    repair = deepcopy(stage3.condenser_repair_contract())
    repair["modelCleanup"].update(
        {
            "sourceVertices": 1610,
            "sourcePolygons": 3240,
            "repairedVertices": 1451,
            "repairedPolygons": 1325,
            "sourceMeshRestored": True,
            "temporaryMeshRemoved": True,
        }
    )
    repair["occlusion"].update(
        {"followsRoot": True, "originalParentRestored": True}
    )
    repair["animation"].update(
        {"locationChannelCount": 3, "temporaryActionRemoved": True}
    )
    manifest = {
        "schema": "twinkle-stage3-condenser-lowres-repair-v1",
        "unit": CONDENSER,
        "selectedFormat": "lossless-png-sequence",
        "render": {
            "resolution": [640, 450],
            "samples": 64,
            "fps": 24,
            "durationMs": 1000,
            "frameCount": 25,
        },
        "motion": {
            "frameIndices": list(range(25)),
            "closeFrameIndices": list(reversed(range(25))),
            "progress": progress_values,
        },
        "frames": frames,
        "repair": repair,
        "quality": {"blackFrameCount": 0, "duplicateAdjacentFrameCount": 0},
        "machinePassed": True,
        "humanVisualApproved": False,
        "authorizesStep6": False,
        "candidateBlendSaved": False,
        "inventorySha256": {},
    }
    (output / "condenser-repair-manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    report = stage3.validate_condenser_repair_candidate(output)
    assert report["schema"] == "twinkle-stage3-condenser-lowres-repair-v1"
    assert report["unit"] == CONDENSER
    assert report["render"] == {
        "resolution": [640, 450],
        "samples": 64,
        "fps": 24,
        "durationMs": 1000,
        "frameCount": 25,
    }
    repair = report["repair"]
    assert repair["attempt"] == 1
    assert repair["rootCause"]["classification"] == (
        "cad-triangulated-geometry-and-surface-normals"
    )
    assert repair["modelCleanup"]["method"] == "temporary-mesh-limited-dissolve"
    assert repair["modelCleanup"]["object"] == (
        "ACL25416U_MOUNT_Red2 :: 实体1"
    )
    assert repair["modelCleanup"]["repairedPolygons"] < (
        repair["modelCleanup"]["sourcePolygons"]
    )
    assert repair["modelCleanup"]["sourceMeshRestored"] is True
    assert repair["modelCleanup"]["temporaryMeshRemoved"] is True
    assert repair["occlusion"] == {
        "method": "reuse-cad-occluder-group-follow-root",
        "group": "OCCLUDER_GROUP__f_dual_acl_housing",
        "meshes": ["FrontCover :: 实体1", "Side1 :: 实体1"],
        "syntheticMeshesCreated": 0,
        "followsRoot": True,
        "originalParentRestored": True,
    }
    assert repair["animation"]["method"] == "native-fcurve"
    assert repair["animation"]["frameRange"] == [0, 24]
    assert repair["animation"]["locationChannelCount"] == 3
    assert repair["animation"]["keyframesPerLocationChannel"] == 25
    assert repair["animation"]["interpolation"] == "BEZIER"
    assert repair["animation"]["handleType"] == "AUTO_CLAMPED"
    assert repair["animation"]["temporaryActionRemoved"] is True
    assert repair["postprocess"] == {
        "method": "none",
        "removelogoApplied": False,
    }
    assert len(report["frames"]) == 25
    assert report["quality"]["blackFrameCount"] == 0
    assert report["quality"]["duplicateAdjacentFrameCount"] == 0
    assert report["machinePassed"] is True
    assert report["humanVisualApproved"] is False
    assert report["authorizesStep6"] is False
    assert report["candidateBlendSaved"] is False


def test_condenser_second_repair_contract_is_exact():
    assert stage3.condenser_second_repair_contract() == {
        "attempt": 2,
        "geometry": {
            "method": "boundary-ring-front-face-replacement",
            "object": "ACL25416U_MOUNT_Red2 :: 实体1",
            "maxFrontOffsetM": 0.0001,
            "fill": "2d-curve-with-inner-rings",
            "solidifyThicknessM": 0.0002,
            "bevelWidthM": 0.00005,
            "replacesOriginalFrontFaces": True,
        },
        "occlusion": {
            "method": "localized-extruded-leak-wedges",
            "preservedMeshes": ["FrontCover :: 实体1", "Side1 :: 实体1"],
            "minimumClearanceM": 0.0005,
            "productStructureClaimed": False,
            "linerCount": 2,
            "rayRois": ["lowerLeftBoard", "centralWhiteCorner"],
        },
        "motion": {
            "driver": "single-travel-property",
            "keyframes": [[0, 0.0], [3, 0.0], [7, 0.06], [19, 0.90], [24, 1.0]],
            "interpolation": "BEZIER",
            "handleType": "AUTO_CLAMPED",
            "autoSmoothing": "CONT_ACCEL",
        },
    }


def test_condenser_r1_linefix_contract_reuses_probe_r1_exact_boolean_only():
    contract = stage3.condenser_r1_linefix_contract()
    assert contract == {
        "geometry": {
            "method": "exact-boolean-front-skin-proxy",
            "object": "ACL25416U_MOUNT_Red2 :: 实体1",
            "operation": "INTERSECT",
            "solver": "EXACT",
            "maxFrontOffsetM": 0.00005,
        },
        "motion": {
            "frameIndices": [0, 12, 24],
            "progress": [0.0, 0.5, 1.0],
            "source": "condenser-lowres-r1",
        },
        "occlusion": {"method": "none", "linerCount": 0},
        "postprocess": {"method": "none"},
    }


def test_condenser_r1_linefix_command_keeps_original_probe_worker_scope(tmp_path):
    output = tmp_path.resolve()
    command = stage3.condenser_r1_linefix_probe_blender_command(
        "blender.exe", "candidate.blend", output
    )
    python_index = command.index("--python")
    assert command[python_index - 2 : python_index] == ["--python-exit-code", "1"]
    assert command[-2:] == [
        "--stage3-condenser-r1-linefix-probe-worker",
        str(output),
    ]


def test_condenser_r1_linefix_worker_contains_exact_boolean_but_no_liner():
    source = Path(stage3.__file__).read_text(encoding="utf-8")
    start = source.index("def blender_condenser_r1_linefix_probe_worker")
    end = source.index("\ndef blender_condenser_second_repair_probe_worker", start)
    worker = source[start:end]
    assert 'boolean.operation = "INTERSECT"' in worker
    assert 'boolean.solver = "EXACT"' in worker
    assert "CAVITY_LINER" not in worker
    assert "primitive_cube_add(location=liner_center)" not in worker


def test_condenser_r1_linefix_candidate_contract_keeps_r1_behavior():
    contract = stage3.condenser_r1_linefix_candidate_contract()
    assert contract["schema"] == "twinkle-stage3-condenser-r1-linefix-v1"
    assert contract["render"] == {
        "resolution": [640, 450],
        "samples": 64,
        "fps": 24,
        "durationMs": 1000,
        "frameCount": 25,
    }
    assert contract["motion"] == {
        "frameIndices": list(range(25)),
        "closeFrameIndices": list(reversed(range(25))),
        "progress": [stage3.condenser_motion_progress(i) for i in range(25)],
        "source": "condenser-lowres-r1",
    }
    assert contract["geometry"] == stage3.condenser_r1_linefix_contract()["geometry"]
    assert contract["occlusion"] == {"method": "none", "linerCount": 0}
    assert contract["postprocess"] == {"method": "none"}
    assert contract["humanVisualApproved"] is False
    assert contract["authorizesStep6"] is False


def test_condenser_r1_linefix_full_command_uses_same_worker(tmp_path):
    output = tmp_path.resolve()
    command = stage3.condenser_r1_linefix_blender_command(
        "blender.exe", "candidate.blend", output
    )
    python_index = command.index("--python")
    assert command[python_index - 2 : python_index] == ["--python-exit-code", "1"]
    assert command[-2:] == ["--stage3-condenser-r1-linefix-worker", str(output)]


def test_condenser_r1_linefix_validator_keeps_r1_and_rejects_liner(tmp_path):
    frames_root = tmp_path / "frames"
    frames_root.mkdir()
    frames = []
    for index in range(25):
        path = frames_root / f"frame-{index:03d}.png"
        Image.new("RGB", (640, 450), (30 + index, 40 + index, 50 + index)).save(path)
        frames.append(
            {
                "index": index,
                "progress": stage3.condenser_motion_progress(index),
                "path": f"frames/{path.name}",
                "sha256": stage3.sha256(path),
            }
        )
    for relative in stage3.CONDENSER_LOWRES_REVIEW_FILES:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix == ".png":
            Image.new("RGB", (1, 1), "white").save(path)
        else:
            path.write_text("{}", encoding="utf-8")
    contract = stage3.condenser_r1_linefix_candidate_contract()
    manifest = {
        **contract,
        "unit": CONDENSER,
        "selectedFormat": "lossless-png-sequence",
        "frames": frames,
        "candidateBlendSaved": False,
        "temporaryDataBlocksRemaining": [],
        "machinePassed": True,
        "inventorySha256": {},
    }
    (tmp_path / "condenser-linefix-manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    report = stage3.validate_condenser_r1_linefix_candidate(tmp_path)
    assert report["motion"]["progress"] == [
        stage3.condenser_motion_progress(index) for index in range(25)
    ]
    assert report["geometry"]["method"] == "exact-boolean-front-skin-proxy"
    assert report["occlusion"] == {"method": "none", "linerCount": 0}

    manifest["occlusion"]["linerCount"] = 1
    (tmp_path / "condenser-linefix-manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="liner"):
        stage3.validate_condenser_r1_linefix_candidate(tmp_path)


def test_visual_failure_measurement_detects_line_and_white_leaks(tmp_path):
    frames = tmp_path / "frames"
    frames.mkdir()
    for index in (12, 18):
        image = Image.new("RGB", (640, 450), (96, 104, 112))
        draw = ImageDraw.Draw(image)
        if index == 18:
            draw.line((430, 120, 430, 340), fill=(4, 4, 4), width=2)
            draw.polygon(
                ((12, 336), (151, 336), (151, 404), (12, 404)),
                fill=(250, 250, 250),
            )
        else:
            draw.polygon(
                ((34, 324), (184, 324), (184, 390), (34, 390)),
                fill=(250, 250, 250),
            )
        image.save(frames / f"frame-{index:03d}.png")

    report = stage3.measure_condenser_visual_failures(tmp_path)
    assert report["rightPlateLine"]["longestRunPx"] > 12
    assert report["lowerLeftBoard"]["nearWhitePixels"] > 0
    assert report["centralWhiteCorner"]["nearWhitePixels"] > 0


def test_second_repair_probe_command_keeps_exception_gate_and_absolute_scope(tmp_path):
    output = tmp_path.resolve()
    command = stage3.condenser_second_repair_probe_blender_command(
        "blender.exe", "candidate.blend", output
    )
    python_index = command.index("--python")
    assert command[python_index - 2 : python_index] == ["--python-exit-code", "1"]
    assert command[-2:] == [
        "--stage3-condenser-second-repair-probe-worker",
        str(output),
    ]


def test_second_repair_probe_audit_is_bounded_and_restored(tmp_path):
    frame_records = []
    for index in (0, 12, 24):
        path = tmp_path / f"frame-{index:03d}.png"
        Image.new("RGB", (640, 450), (40 + index, 40 + index, 40 + index)).save(path)
        frame_records.append(
            {"index": index, "path": path.name, "sha256": stage3.sha256(path)}
        )
    audit = {
        "schema": "twinkle-stage3-condenser-second-repair-probe-v1",
        "frameIndices": [0, 12, 24],
        "candidateBlendSha256Before": "A" * 64,
        "candidateBlendSha256After": "A" * 64,
        "candidateBlendSaved": False,
        "geometry": {
            "method": "boundary-ring-front-face-replacement",
            "proxyCreated": True,
            "nonManifoldEdges": 0,
            "zeroAreaFaces": 0,
            "visibleOpeningCountMatches": True,
            "maxFrontOffsetM": 0.00005,
            "outerRingCount": 1,
            "innerRingCount": 5,
            "ringAuditMatches": True,
            "replacesOriginalFrontFaces": True,
        },
        "occlusion": {
            "method": "localized-extruded-leak-wedges",
            "classification": "render-only-cavity-liner",
            "productStructureClaimed": False,
            "preservedOccluderParents": True,
            "minimumClearanceM": 0.0006,
            "linerCount": 2,
            "roiOutsideChangedPixels": 0,
        },
        "temporaryDataBlocksRemaining": [],
        "frames": frame_records,
    }
    (tmp_path / "probe-audit.json").write_text(json.dumps(audit), encoding="utf-8")

    report = stage3.validate_condenser_second_repair_probe(tmp_path)
    assert report["frameIndices"] == [0, 12, 24]
    assert report["geometry"]["maxFrontOffsetM"] <= 0.0001
    assert report["occlusion"]["minimumClearanceM"] >= 0.0005
    assert report["candidateBlendSaved"] is False


def test_blender_probe_worker_does_not_call_host_pillow_validator():
    source = Path(stage3.__file__).read_text(encoding="utf-8")
    start = source.index("def blender_condenser_second_repair_probe_worker")
    end = source.index("\ndef _stage3_cli", start)
    worker_source = source[start:end]
    assert "validate_condenser_second_repair_probe(output_root)" not in worker_source


def test_probe_validator_rejects_boolean_overlay_and_broad_box(tmp_path):
    frames = []
    for index in (0, 12, 24):
        path = tmp_path / f"frame-{index:03d}.png"
        Image.new("RGB", (640, 450), (64, 64, 64)).save(path)
        frames.append({"index": index, "path": path.name, "sha256": stage3.sha256(path)})
    old_probe = {
        "schema": "twinkle-stage3-condenser-second-repair-probe-v1",
        "frameIndices": [0, 12, 24],
        "candidateBlendSha256Before": "A" * 64,
        "candidateBlendSha256After": "A" * 64,
        "candidateBlendSaved": False,
        "geometry": {
            "method": "exact-boolean-front-skin-proxy",
            "proxyCreated": True,
            "nonManifoldEdges": 0,
            "zeroAreaFaces": 0,
            "visibleOpeningCountMatches": True,
            "maxFrontOffsetM": 0.00005,
        },
        "occlusion": {
            "method": "fixed-render-only-cavity-liner",
            "classification": "render-only-cavity-liner",
            "productStructureClaimed": False,
            "preservedOccluderParents": True,
            "minimumClearanceM": 0.0006,
            "linerCount": 1,
        },
        "temporaryDataBlocksRemaining": [],
        "frames": frames,
    }
    (tmp_path / "probe-audit.json").write_text(
        json.dumps(old_probe), encoding="utf-8"
    )

    with pytest.raises(ValueError, match="revised second repair"):
        stage3.validate_condenser_second_repair_probe(tmp_path)


def test_finalize_probe_visual_audit_limits_wedge_changes_to_failure_rois(tmp_path):
    for index in (0, 12, 24):
        control = Image.new("RGB", (640, 450), (88, 96, 104))
        final = control.copy()
        if index == 12:
            ImageDraw.Draw(control).polygon(
                ((34, 324), (184, 324), (184, 390), (34, 390)),
                fill=(250, 250, 250),
            )
            ImageDraw.Draw(final).polygon(
                ((34, 324), (184, 324), (184, 390), (34, 390)),
                fill=(8, 8, 8),
            )
        if index == 24:
            ImageDraw.Draw(control).polygon(
                ((12, 336), (151, 336), (151, 404), (12, 404)),
                fill=(250, 250, 250),
            )
            ImageDraw.Draw(final).polygon(
                ((12, 336), (151, 336), (151, 404), (12, 404)),
                fill=(8, 8, 8),
            )
        control.save(tmp_path / f"control-frame-{index:03d}.png")
        final.save(tmp_path / f"frame-{index:03d}.png")
    audit = {
        "occlusion": {
            "linerCount": 2,
            "roiOutsideChangedPixels": None,
        }
    }
    (tmp_path / "probe-audit.json").write_text(json.dumps(audit), encoding="utf-8")

    report = stage3.finalize_condenser_second_repair_probe_visual_audit(tmp_path)
    assert report["occlusion"]["roiOutsideChangedPixels"] == 0
    assert report["visualGates"]["rightPlateLine"]["passed"] is True
    assert report["visualGates"]["lowerLeftBoard"]["nearWhitePixels"] == 0
    assert report["visualGates"]["centralWhiteCorner"]["nearWhitePixels"] == 0


def test_condenser_motion_only_probe_contract_is_strictly_isolated():
    assert stage3.condenser_motion_only_probe_contract() == {
        "schema": "twinkle-stage3-condenser-motion-only-probe-v1",
        "unit": CONDENSER,
        "movingAssembly": "SHOWCASE_GROUP__f_dual_acl_housing",
        "render": {
            "resolution": [640, 450],
            "samples": 64,
            "fps": 24,
            "durationMs": 1000,
            "frameCount": 25,
        },
        "travel": {
            "property": "travel",
            "range": [0.0, 1.0],
            "keyframes": [[0, 0.0], [3, 0.0], [7, 0.06], [19, 0.9], [24, 1.0]],
            "interpolation": "BEZIER",
            "handleType": "AUTO_CLAMPED",
            "autoSmoothing": "CONT_ACCEL",
            "animatedFcurveCount": 1,
            "locationDriverCount": 0,
            "vectorDerivationCount": 1,
            "locationKeyframeCount": 0,
            "rotationKeyframeCount": 0,
        },
        "fullOffsetM": [0.034, 0.012, -0.016],
        "closeFrameIndices": list(reversed(range(25))),
        "geometryChanges": 0,
        "materialChanges": 0,
        "lightChanges": 0,
        "cameraChanges": 0,
        "postprocess": "none",
        "candidateBlendSaved": False,
        "humanVisualApproved": False,
        "authorizesR3": False,
        "authorizesStep6": False,
    }


def test_motion_only_runtime_rejects_old_three_axis_per_frame_fcurves():
    legacy_runtime = {
        "travel": {
            "animatedFcurveCount": 0,
            "locationDriverCount": 3,
            "vectorDerivationCount": 0,
            "locationKeyframeCount": 75,
            "rotationKeyframeCount": 0,
            "keyframes": [],
            "interpolation": "BEZIER",
            "handleType": "AUTO_CLAMPED",
            "autoSmoothing": "NONE",
        }
    }
    with pytest.raises(ValueError, match="single travel freedom"):
        stage3.validate_condenser_motion_only_runtime(legacy_runtime)


def test_motion_only_runtime_accepts_five_pose_rigid_collinear_kinematics():
    progress = [
        0.0,
        0.0,
        0.0,
        0.0,
        0.004,
        0.014,
        0.032,
        0.06,
        0.11,
        0.18,
        0.27,
        0.38,
        0.50,
        0.61,
        0.70,
        0.77,
        0.82,
        0.86,
        0.885,
        0.90,
        0.934,
        0.961,
        0.981,
        0.995,
        1.0,
    ]
    velocity = [
        0.0,
        0.0,
        0.0,
        0.0,
        0.006,
        0.014,
        0.023,
        0.038,
        0.060,
        0.080,
        0.105,
        0.120,
        0.120,
        0.105,
        0.085,
        0.065,
        0.050,
        0.038,
        0.026,
        0.020,
        0.017,
        0.013,
        0.009,
        0.004,
        0.0,
    ]
    full_offset = [0.034, 0.012, -0.016]
    runtime = {
        "travel": {
            "property": "travel",
            "range": [0.0, 1.0],
            "animatedFcurveCount": 1,
            "locationDriverCount": 0,
            "vectorDerivationCount": 1,
            "locationKeyframeCount": 0,
            "rotationKeyframeCount": 0,
            "keyframes": [[0, 0.0], [3, 0.0], [7, 0.06], [19, 0.9], [24, 1.0]],
            "interpolation": "BEZIER",
            "handleType": "AUTO_CLAMPED",
            "autoSmoothing": "CONT_ACCEL",
        },
        "progress": progress,
        "velocityPerFrame": velocity,
        "accelerationPerFrame": [
            velocity[index] - velocity[index - 1] if index else 0.0
            for index in range(25)
        ],
        "componentOffsetsM": [
            [value * sample for value in full_offset] for sample in progress
        ],
        "rigidRelativeMatrixHashes": ["FLOAT-A", "FLOAT-B"] + ["FLOAT-A"] * 23,
        "rigidLocalMatrixHashes": ["FLOAT-A", "FLOAT-B"] + ["FLOAT-A"] * 23,
        "rigidMaxRelativeMatrixDrift": [0.0, 5.960464477539063e-08] + [0.0] * 23,
        "closeFrameIndices": list(reversed(range(25))),
        "pauseEvidence": {
            "frameIndex": 7,
            "heldFrameIndex": 7,
            "resumeFrameIndex": 8,
            "directionBefore": "forward",
            "directionAfter": "forward",
        },
    }
    report = stage3.validate_condenser_motion_only_runtime(runtime)
    assert report["progress"][7] == 0.06
    assert report["progress"][19] == 0.9
    assert report["velocityPerFrame"][24] == 0.0

    runtime["rigidMaxRelativeMatrixDrift"][1] = 1.1e-7
    with pytest.raises(ValueError, match="not rigid"):
        stage3.validate_condenser_motion_only_runtime(runtime)


def test_motion_only_probe_command_is_isolated_and_non_saving(tmp_path):
    output = tmp_path.resolve()
    command = stage3.condenser_motion_only_probe_blender_command(
        "blender.exe", "candidate.blend", output
    )
    python_index = command.index("--python")
    assert command[python_index - 2 : python_index] == ["--python-exit-code", "1"]
    assert command[-2:] == [
        "--stage3-condenser-motion-only-probe-worker",
        str(output),
    ]
    assert "--save" not in command


def test_motion_only_worker_uses_one_travel_curve_and_no_visual_repairs():
    source = Path(stage3.__file__).read_text(encoding="utf-8")
    start = source.index("def blender_condenser_motion_only_probe_worker")
    end = source.index("\ndef blender_condenser_second_repair_probe_worker", start)
    worker = source[start:end]
    assert 'motion_root["travel"] = 0.0' in worker
    assert 'data_path=\'["travel"]\'' in worker
    assert "keyframe_points.add(5)" in worker
    assert 'travel_curve.auto_smoothing = "CONT_ACCEL"' in worker
    assert "motion_root.location = full_offset * progress" in worker
    assert 'motion_root.driver_add("location", axis)' not in worker
    assert 'driver_add("rotation_euler"' not in worker
    assert 'data_path="location"' not in worker
    assert "bmesh" not in worker
    assert "Boolean" not in worker
    assert "material" not in worker.lower()
    assert "light" not in worker.lower()
    assert "removelogo" not in worker.lower()
    assert "CAVITY_LINER" not in worker


def test_motion_only_worker_uses_blender_52_recursive_children_api():
    source = Path(stage3.__file__).read_text(encoding="utf-8")
    start = source.index("def blender_condenser_motion_only_probe_worker")
    end = source.index("\ndef blender_condenser_second_repair_probe_worker", start)
    worker = source[start:end]
    assert "root.children_recursive" in worker
    assert "parent_recursive" not in worker


def test_motion_only_review_inventory_is_exact():
    assert stage3.CONDENSER_MOTION_ONLY_REVIEW_FILES == (
        "review/old-new-same-frame-contact-sheet.png",
        "review/keyframes-contact-sheet.png",
        "review/kinematics-curves.png",
        "review/pause-resume-contact-sheet.png",
        "review/index.html",
        "motion-runtime.json",
    )


def test_motion_only_probe_validator_requires_manifest(tmp_path):
    with pytest.raises(FileNotFoundError, match="motion-only probe manifest"):
        stage3.validate_condenser_motion_only_probe(tmp_path)


def test_motion_only_probe_output_name_cannot_be_r3(tmp_path):
    with pytest.raises(ValueError, match="motion-only probe"):
        stage3.build_condenser_motion_only_probe(
            tmp_path / "condenser-lowres-r3", blender="blender.exe"
        )


def test_motion_only_quality_uses_progress_hold_and_bounded_eevee_noise():
    assert stage3.motion_only_quality_passes(
        {"blackFrameCount": 0, "endpointMaeVsApprovedLinefix": 0.00131134}
    )
    assert not stage3.motion_only_quality_passes(
        {"blackFrameCount": 1, "endpointMaeVsApprovedLinefix": 0.0}
    )
    assert not stage3.motion_only_quality_passes(
        {"blackFrameCount": 0, "endpointMaeVsApprovedLinefix": 0.01000001}
    )


def test_motion_playback_controller_exercises_pause_resume_and_reverse_close():
    forward = stage3.motion_playback_state("expand")
    for _ in range(7):
        forward = stage3.reduce_motion_playback(forward, "tick")
    assert forward["frame"] == 7
    forward = stage3.reduce_motion_playback(forward, "pause")
    held = stage3.reduce_motion_playback(forward, "tick")
    assert held["frame"] == 7
    forward = stage3.reduce_motion_playback(held, "resume")
    forward = stage3.reduce_motion_playback(forward, "tick")
    assert forward["frame"] == 8
    while not forward["ended"]:
        forward = stage3.reduce_motion_playback(forward, "tick")
    assert forward["frame"] == 24

    close = stage3.motion_playback_state("close")
    visited = [close["frame"]]
    while not close["ended"]:
        close = stage3.reduce_motion_playback(close, "tick")
        visited.append(close["frame"])
    assert visited == list(reversed(range(25)))
    assert close["frame"] == 0


def test_motion_playback_audit_binds_exercised_sequences():
    assert stage3.motion_playback_audit() == {
        "expandFrameIndices": list(range(25)),
        "closeFrameIndices": list(reversed(range(25))),
        "pause": {
            "pausedFrame": 7,
            "heldFrame": 7,
            "resumedFrame": 8,
            "directionBefore": "forward",
            "directionAfter": "forward",
        },
        "expandEndedFrame": 24,
        "closeEndedFrame": 0,
    }


def test_motion_only_human_approval_does_not_authorize_r3_or_step6():
    approved = stage3.motion_only_human_approval(
        {
            "unit": CONDENSER,
            "machinePassed": True,
            "humanVisualApproved": False,
            "authorizesR3": False,
            "authorizesStep6": False,
        },
        approved_on="2026-08-28",
    )
    assert approved["humanVisualApproved"] is True
    assert approved["humanApproval"] == {
        "approvedUnit": CONDENSER,
        "approvedBy": "user",
        "approvedOn": "2026-08-28",
        "scope": "stage3-step5-condenser-motion-only-probe",
        "authorizesR3": False,
        "authorizesStep6": False,
    }
    assert approved["authorizesR3"] is False
    assert approved["authorizesStep6"] is False

    with pytest.raises(ValueError, match="machine-passed"):
        stage3.motion_only_human_approval(
            {
                "unit": CONDENSER,
                "machinePassed": False,
                "humanVisualApproved": False,
                "authorizesR3": False,
                "authorizesStep6": False,
            },
            approved_on="2026-08-28",
        )


def test_linefix_human_approval_records_the_existing_visual_gate_only():
    approved = stage3.linefix_human_approval(
        {
            "unit": CONDENSER,
            "machinePassed": True,
            "humanVisualApproved": False,
            "authorizesStep6": False,
        },
        approved_on="2026-08-27",
    )
    assert approved["humanVisualApproved"] is True
    assert approved["humanApproval"] == {
        "approvedUnit": CONDENSER,
        "approvedBy": "user",
        "approvedOn": "2026-08-27",
        "scope": "stage3-step5-condenser-r1-linefix",
        "authorizesStep6": False,
    }
    assert approved["authorizesStep6"] is False


def test_condenser_r3_contract_closes_step5_without_authorizing_step6():
    contract = stage3.condenser_r3_candidate_contract()
    assert contract == {
        "schema": "twinkle-stage3-condenser-lowres-r3-v1",
        "unit": CONDENSER,
        "selectedFormat": "lossless-png-sequence",
        "render": {
            "resolution": [640, 450],
            "samples": 64,
            "fps": 24,
            "durationMs": 1000,
            "frameCount": 25,
        },
        "frameIndices": list(range(25)),
        "closeFrameIndices": list(reversed(range(25))),
        "visualSource": "approved-condenser-r1-linefix",
        "motionSource": "approved-condenser-motion-only-probe",
        "promotionMethod": "byte-identical-approved-frame-promotion",
        "candidateBlendSaved": False,
        "humanVisualApproved": True,
        "step5Closed": True,
        "authorizesStep6": False,
    }


def test_motion_manifest_syncs_the_recorded_linefix_approval_without_broadening_scope():
    synced = stage3.sync_motion_visual_baseline_approval(
        {
            "visualBaseline": {
                "path": "output/linefix",
                "manifestSha256": "OLD",
                "humanVisualApproved": True,
            },
            "humanVisualApproved": True,
            "authorizesR3": False,
            "authorizesStep6": False,
        },
        linefix_manifest_sha256="ABC123",
        approved_on="2026-08-27",
    )
    assert synced["visualBaseline"] == {
        "path": "output/linefix",
        "manifestSha256": "ABC123",
        "humanVisualApproved": True,
        "approvalSource": "recorded linefix human approval on 2026-08-27",
    }
    assert synced["humanVisualApproved"] is True
    assert synced["authorizesR3"] is False
    assert synced["authorizesStep6"] is False


def test_condenser_r3_promotes_the_approved_combined_frames_byte_identically(tmp_path, stage3_evidence):
    output = tmp_path / "condenser-lowres-r3"
    report = stage3.build_condenser_r3_candidate(output)
    motion = stage3.validate_condenser_motion_only_probe(
        stage3.CONDENSER_MOTION_ONLY_OUTPUT_ROOT
    )

    assert report["machinePassed"] is True
    assert report["humanVisualApproved"] is True
    assert report["step5Closed"] is True
    assert report["authorizesStep6"] is False
    assert report["sourceFrameSha256"] == [
        frame["sha256"] for frame in motion["newFrames"]
    ]
    assert [frame["sha256"] for frame in report["frames"]] == report[
        "sourceFrameSha256"
    ]
    review_html = (output / "review" / "index.html").read_text(encoding="utf-8")
    assert '<link rel="icon" href="data:image/svg+xml,' in review_html
    assert "pauseButton.textContent='暂停'" in review_html
    assert not list(output.rglob("*.blend"))

    (output / "unexpected.tmp").write_text("not inventory", encoding="utf-8")
    with pytest.raises(ValueError, match="inventory"):
        stage3.validate_condenser_r3_candidate(output)

    with pytest.raises(ValueError, match="condenser-lowres-r3"):
        stage3.build_condenser_r3_candidate(tmp_path / "wrong-name")


def test_condenser_r3_restores_staging_when_final_directory_validation_fails(
    tmp_path, monkeypatch, stage3_evidence
):
    output = tmp_path / "condenser-lowres-r3"
    real_validator = stage3.validate_condenser_r3_candidate

    def fail_only_after_promotion(candidate):
        candidate = Path(candidate)
        if candidate.name == "condenser-lowres-r3":
            raise ValueError("simulated final-path source drift")
        return real_validator(candidate)

    monkeypatch.setattr(
        stage3, "validate_condenser_r3_candidate", fail_only_after_promotion
    )
    with pytest.raises(RuntimeError, match="staging restored"):
        stage3.build_condenser_r3_candidate(output)
    assert not output.exists()
    staging = list(tmp_path.glob(".condenser-r3-*"))
    assert len(staging) == 1
    assert (staging[0] / "condenser-r3-manifest.json").is_file()


def test_formal_candidate_contract_freezes_the_approved_step6_scope():
    assert stage3.FORMAL_OUTPUT_ROOT == (
        ROOT / "output" / "twinkle-stage3-dual-hotspot-motion-r1"
    )
    assert stage3.formal_candidate_contract() == {
        "schema": "twinkle-stage3-dual-hotspot-motion-v1",
        "selectedFormat": "lossless-png-sequence",
        "render": {
            "resolution": [1280, 900],
            "samples": 512,
            "fps": 24,
            "durationMs": 1000,
            "frameCountPerUnit": 25,
        },
        "units": [CHAMBER, CONDENSER],
        "frameIndices": list(range(25)),
        "closeFrameIndices": list(reversed(range(25))),
        "outputDirectoryName": "twinkle-stage3-dual-hotspot-motion-r1",
        "candidateBlendSaved": False,
        "writeProductionPage": False,
        "humanVisualApproved": False,
        "step6MachinePassed": False,
        "authorizesStep7": False,
    }


def test_stage3_closeout_contract_is_r2_and_never_authorizes_stage4():
    assert stage3.STAGE3_CLOSEOUT_OUTPUT_ROOT == (
        ROOT / "output" / "twinkle-stage3-dual-hotspot-motion-r2"
    )
    assert stage3.stage3_closeout_contract() == {
        "schema": "twinkle-stage3-dual-hotspot-motion-r2-v1",
        "selectedFormat": "lossless-png-sequence",
        "render": {
            "resolution": [1280, 900],
            "samples": 512,
            "fps": 24,
            "durationMs": 1000,
            "frameCountPerUnit": 25,
        },
        "units": [CHAMBER, CONDENSER],
        "frameIndices": list(range(25)),
        "closeFrameIndices": list(reversed(range(25))),
        "outputDirectoryName": "twinkle-stage3-dual-hotspot-motion-r2",
        "candidateBlendSaved": False,
        "writeProductionPage": False,
        "humanVisualApproved": False,
        "machinePassed": False,
        "authorizesStage3Close": False,
        "stage3Closed": False,
        "authorizesStage4": False,
    }


def _synthetic_closeout_condenser_renderer(staging, authority, blender=None):
    unit_root = staging / "units" / CONDENSER
    frames_root = unit_root / "frames"
    frames_root.mkdir(parents=True)
    frames = []
    progress = stage3.approved_motion_progress()
    for index in range(25):
        path = frames_root / f"frame-{index:03d}.png"
        Image.new(
            "RGBA",
            (1280, 900),
            (75 + index * 4, 105 + index * 3, 135 + index * 2, 255),
        ).save(path)
        frames.append(
            {
                "index": index,
                "progress": progress[index],
                "path": path.relative_to(staging).as_posix(),
                "sha256": stage3.sha256(path),
            }
        )
    unit = authority["units"][CONDENSER]
    motion = stage3.validate_condenser_motion_only_probe(
        stage3.CONDENSER_MOTION_ONLY_OUTPUT_ROOT
    )
    audit = {
        "schema": stage3.STAGE3_CLOSEOUT_WORKER_SCHEMA,
        "unit": CONDENSER,
        "render": stage3.FORMAL_RENDER,
        "frameIndices": list(range(25)),
        "cameraPresetId": unit["cameraPresetId"],
        "camera": unit["camera"],
        "rootObjects": unit["rootObjects"],
        "fullOffsetsM": unit["fullOffsetsM"],
        "lightRigHash": authority["renderProfile"]["lightRigHash"],
        "materialRuleHash": authority["renderProfile"]["materialRuleHash"],
        "colorManagementHash": authority["renderProfile"]["colorManagementHash"],
        "candidateBlendSha256Before": stage3.EXPECTED_CANDIDATE_BLEND_SHA256,
        "candidateBlendSha256After": stage3.EXPECTED_CANDIDATE_BLEND_SHA256,
        "candidateBlendSaved": False,
        "temporaryDataBlocksRemaining": [],
        "linefix": stage3.condenser_r1_linefix_contract(),
        "motionSource": "approved-condenser-motion-only-probe",
        "motionRuntime": motion["motionRuntime"],
        "frames": frames,
    }
    (unit_root / "render-audit.json").write_text(
        json.dumps(audit, indent=2), encoding="utf-8"
    )
    return audit


def test_stage3_closeout_builds_r2_then_requires_narrow_human_approval(
    tmp_path, stage3_evidence
):
    output = tmp_path / "twinkle-stage3-dual-hotspot-motion-r2"
    report = stage3.build_stage3_closeout_candidate(
        output, renderer=_synthetic_closeout_condenser_renderer
    )
    assert report["machinePassed"] is True
    assert report["humanVisualApproved"] is False
    assert report["authorizesStage3Close"] is False
    assert report["stage3Closed"] is False
    assert report["authorizesStage4"] is False
    assert len(list(output.glob("units/*/frames/*.png"))) == 50
    assert not list(output.rglob("*.blend"))
    assert not list(output.rglob("*.mp4"))

    approved = stage3.record_stage3_closeout_approval(
        output, approved_on="2026-08-28"
    )
    assert approved["humanVisualApproved"] is True
    assert approved["authorizesStage3Close"] is True
    assert approved["stage3Closed"] is True
    assert approved["authorizesStage4"] is False
    assert approved["humanApproval"] == {
        "approvedBy": "user",
        "approvedOn": "2026-08-28",
        "scope": "stage3-step7-r2-closeout",
        "authorizesStage3Close": True,
        "authorizesStage4": False,
    }

    manifest_path = output / "twinkle-stage3-closeout-manifest.json"
    overbroad = json.loads(manifest_path.read_text(encoding="utf-8"))
    overbroad["authorizesStage4"] = True
    manifest_path.write_text(json.dumps(overbroad, indent=2), encoding="utf-8")
    with pytest.raises(ValueError, match="authorizesStage4"):
        stage3.validate_stage3_closeout_candidate(output)

    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        stage3.build_stage3_closeout_candidate(
            output, renderer=_synthetic_closeout_condenser_renderer
        )


def test_stage3_closeout_hash_gate_rejects_frame_tampering(tmp_path, stage3_evidence):
    output = tmp_path / "twinkle-stage3-dual-hotspot-motion-r2"
    stage3.build_stage3_closeout_candidate(
        output, renderer=_synthetic_closeout_condenser_renderer
    )
    frame = output / "units" / CONDENSER / "frames" / "frame-012.png"
    frame.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="frame hash mismatch"):
        stage3.validate_stage3_closeout_candidate(output)


def test_stage3_closeout_renderer_failure_keeps_staging_and_never_publishes(
    tmp_path, stage3_evidence
):
    output = tmp_path / "twinkle-stage3-dual-hotspot-motion-r2"

    def fail_renderer(staging, authority, blender=None):
        raise RuntimeError("injected closeout render failure")

    with pytest.raises(RuntimeError, match="staging kept"):
        stage3.build_stage3_closeout_candidate(output, renderer=fail_renderer)
    assert not output.exists()
    staging = list(tmp_path.glob(".twinkle-stage3-closeout-*"))
    assert len(staging) == 1
    assert (staging[0] / "units" / CHAMBER / "render-audit.json").is_file()


def test_stage3_closeout_worker_is_full_25_frame_linefix_motion_and_non_saving(
    tmp_path
):
    output = (tmp_path / "closeout-condenser").resolve()
    command = stage3.stage3_closeout_condenser_blender_command(
        "blender.exe", "candidate.blend", output
    )
    assert command[-2:] == ["--stage3-closeout-condenser-worker", str(output)]
    assert "--save" not in command
    source = Path(stage3.__file__).read_text(encoding="utf-8")
    assert "def blender_stage3_closeout_condenser_worker" in source
    assert "frame_indices=tuple(range(25))" in source
    assert 'motionSource": "approved-condenser-motion-only-probe"' in source


def _synthetic_formal_renderer(staging, authority, blender=None):
    audits = {}
    for unit_index, unit_id in enumerate((CHAMBER, CONDENSER)):
        unit_root = staging / "units" / unit_id
        frames_root = unit_root / "frames"
        frames_root.mkdir(parents=True)
        frames = []
        for frame_index in range(25):
            path = frames_root / f"frame-{frame_index:03d}.png"
            Image.new(
                "RGBA",
                (1280, 900),
                (
                    30 + unit_index * 50 + frame_index,
                    50 + frame_index,
                    80 + frame_index,
                    255,
                ),
            ).save(path)
            frames.append(
                {
                    "index": frame_index,
                    "path": path.relative_to(staging).as_posix(),
                    "sha256": stage3.sha256(path),
                }
            )
        unit = authority["units"][unit_id]
        audit = {
            "schema": "twinkle-stage3-formal-render-audit-v1",
            "unit": unit_id,
            "render": stage3.FORMAL_RENDER,
            "cameraPresetId": unit["cameraPresetId"],
            "camera": unit["camera"],
            "rootObjects": unit["rootObjects"],
            "fullOffsetsM": unit["fullOffsetsM"],
            "lightRigHash": authority["renderProfile"]["lightRigHash"],
            "materialRuleHash": authority["renderProfile"]["materialRuleHash"],
            "colorManagementHash": authority["renderProfile"]["colorManagementHash"],
            "candidateBlendSha256Before": authority["candidateBlend"]["sha256"],
            "candidateBlendSha256After": authority["candidateBlend"]["sha256"],
            "candidateBlendSaved": False,
            "temporaryDataBlocksRemaining": [],
            "frames": frames,
        }
        audit_path = unit_root / "render-audit.json"
        audit_path.write_text(json.dumps(audit, indent=2), encoding="utf-8")
        audits[unit_id] = audit
    return audits


def test_formal_candidate_builds_mutually_exclusive_png_inventory_and_waits_for_browser_evidence(
    tmp_path, stage3_evidence,
):
    output = tmp_path / "twinkle-stage3-dual-hotspot-motion-r1"
    report = stage3.build_formal_candidate(
        output, renderer=_synthetic_formal_renderer
    )

    assert report["selectedFormat"] == "lossless-png-sequence"
    assert report["step6MachinePassed"] is False
    assert report["humanVisualApproved"] is False
    assert report["authorizesStep7"] is False
    assert report["browserMatrix"] == {
        "chrome-151": "pending",
        "chrome-for-testing-150": "pending",
        "edge-151": "pending",
        "edge-150": "not-tested",
    }
    assert len(list(output.glob("units/*/frames/*.png"))) == 50
    assert not list(output.rglob("*.mp4"))
    assert not list(output.rglob("*.blend"))
    review_html = (output / "review" / "index.html").read_text(encoding="utf-8")
    assert "prefers-reduced-motion" in review_html
    assert "暂停动作" in review_html
    assert "继续动作" in review_html
    assert "fetch('/result'" in review_html

    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        stage3.build_formal_candidate(output, renderer=_synthetic_formal_renderer)


def test_formal_candidate_only_machine_passes_after_all_required_browser_results(
    tmp_path, stage3_evidence,
):
    output = tmp_path / "twinkle-stage3-dual-hotspot-motion-r1"
    stage3.build_formal_candidate(output, renderer=_synthetic_formal_renderer)
    results = output / "browser-results"
    results.mkdir()
    for browser_id in ("chrome-151", "chrome-for-testing-150", "edge-151"):
        (results / f"{browser_id}.json").write_text(
            json.dumps(
                {
                    "browserId": browser_id,
                    "passed": True,
                    "frameCountPerUnit": 25,
                    "pauseHeld": True,
                    "resumeSameDirection": True,
                    "closeEndedFrame": 0,
                    "reducedMotionStable": True,
                    "consoleErrors": [],
                    "requestFailures": [],
                }
            ),
            encoding="utf-8",
        )

    report = stage3.finalize_formal_browser_evidence(output)
    assert report["step6MachinePassed"] is True
    assert report["machinePassed"] is True
    assert report["humanVisualApproved"] is False
    assert report["authorizesStep7"] is False
    assert set(report["browserMatrix"].values()) == {"passed", "not-tested"}
    assert report["quality"] == {
        CHAMBER: {"blackFrameCount": 0, "adjacentDuplicatePairs": []},
        CONDENSER: {"blackFrameCount": 0, "adjacentDuplicatePairs": []},
    }

    (output / "unexpected.tmp").write_text("not inventory", encoding="utf-8")
    with pytest.raises(ValueError, match="inventory"):
        stage3.validate_formal_candidate(output)


def test_formal_blender_batch_uses_two_bounded_workers_and_fixed_parameters(
    tmp_path, monkeypatch, stage3_evidence
):
    staging = tmp_path / ".twinkle-stage3-formal-test"
    staging.mkdir()
    authority = stage3.validate_authority()
    calls = []

    def fake_run(command, *, cwd=None):
        calls.append(command)
        unit_id = (
            CHAMBER
            if "--stage3-formal-chamber-worker" in command
            else CONDENSER
        )
        unit_root = Path(command[-1])
        frames_root = unit_root / "frames"
        frames_root.mkdir(parents=True)
        frames = []
        for index in range(25):
            path = frames_root / f"frame-{index:03d}.png"
            Image.new("RGBA", (1280, 900), (index + 10, 20, 30, 255)).save(path)
            frames.append(
                {
                    "index": index,
                    "path": path.relative_to(staging).as_posix(),
                    "sha256": stage3.sha256(path),
                }
            )
        unit = authority["units"][unit_id]
        audit = {
            "schema": "twinkle-stage3-formal-render-audit-v1",
            "unit": unit_id,
            "render": stage3.FORMAL_RENDER,
            "cameraPresetId": unit["cameraPresetId"],
            "camera": unit["camera"],
            "rootObjects": unit["rootObjects"],
            "fullOffsetsM": unit["fullOffsetsM"],
            "lightRigHash": authority["renderProfile"]["lightRigHash"],
            "materialRuleHash": authority["renderProfile"]["materialRuleHash"],
            "colorManagementHash": authority["renderProfile"]["colorManagementHash"],
            "candidateBlendSha256Before": authority["candidateBlend"]["sha256"],
            "candidateBlendSha256After": authority["candidateBlend"]["sha256"],
            "candidateBlendSaved": False,
            "temporaryDataBlocksRemaining": [],
            "frames": frames,
        }
        (unit_root / "render-audit.json").write_text(
            json.dumps(audit), encoding="utf-8"
        )

    monkeypatch.setattr(stage3, "run_checked", fake_run)
    audits = stage3.render_formal_batch(
        staging, authority, blender=tmp_path / "blender.exe"
    )

    assert set(audits) == {CHAMBER, CONDENSER}
    assert len(calls) == 2
    assert "--stage3-formal-chamber-worker" in calls[0]
    assert "--stage3-formal-condenser-worker" in calls[1]
    assert all("--background" in command for command in calls)
    assert all(str(command[-1]).startswith(str(staging)) for command in calls)


def test_formal_browser_command_is_local_isolated_and_targets_the_review_page(
    tmp_path,
):
    command = stage3.formal_browser_command(
        tmp_path / "chrome.exe",
        tmp_path / "profile",
        "http://127.0.0.1:8767/review/index.html?browser=chrome-151",
    )
    assert command[0] == str(tmp_path / "chrome.exe")
    assert "--headless=new" in command
    assert f"--user-data-dir={tmp_path / 'profile'}" in command
    assert "--host-resolver-rules=MAP * 0.0.0.0, EXCLUDE 127.0.0.1, EXCLUDE localhost" in command
    assert command[-1].startswith("http://127.0.0.1:8767/review/index.html")


def test_windows_browser_version_uses_environment_for_parenthesized_paths(monkeypatch):
    executable = Path("Program Files (x86)") / "Browser" / "browser.exe"

    def fake_run(command, **kwargs):
        assert "$env:TWINKLE_BROWSER_VERSION_PATH" in command[3]
        assert len(command) == 4
        assert kwargs["env"]["TWINKLE_BROWSER_VERSION_PATH"] == str(executable)
        return SimpleNamespace(returncode=0, stdout="151.0.1.2\n", stderr="")

    monkeypatch.setattr(stage3.subprocess, "run", fake_run)
    assert stage3._windows_product_version(executable) == "151.0.1.2"


def test_step7_limited_probe_contract_reuses_only_the_approved_visual_and_motion_paths():
    assert stage3.STEP7_PROBE_FRAMES == (0, 20, 21, 22, 24)
    assert stage3.STEP7_PROBE_OUTPUT_ROOT == (
        ROOT
        / "output"
        / ".twinkle-stage3-step7-limited-repair-20260828"
        / "condenser-hd-probe-r1"
    )
    contract = stage3.step7_probe_contract()
    assert contract["render"] == stage3.FORMAL_RENDER
    assert contract["frameIndices"] == [0, 20, 21, 22, 24]
    assert contract["linefix"] == {
        "geometry": stage3.condenser_r1_linefix_contract()["geometry"],
        "occlusion": {"method": "none", "linerCount": 0},
        "postprocess": {"method": "none"},
    }
    assert contract["motion"] == {
        "source": "approved-condenser-motion-only-probe",
        "property": "travel",
        "fullOffsetM": [0.034, 0.012, -0.016],
    }
    assert contract["endpointPolicy"] == (
        "render-both-endpoints-through-approved-linefix-worker"
    )
    assert contract["chamberMechanicalFramesRerendered"] is False
    assert contract["humanVisualApproved"] is False
    assert contract["authorizesFull25"] is False
    assert contract["authorizesFormalReplacement"] is False


def test_step7_probe_worker_uses_the_same_linefix_motion_worker_for_all_five_frames():
    source = Path(stage3.__file__).read_text(encoding="utf-8")
    start = source.index("def blender_step7_probe_worker")
    end = source.index("\ndef blender_condenser_repair_worker", start)
    worker = source[start:end]
    assert "blender_condenser_motion_only_probe_worker(" in worker
    assert "frame_indices=STEP7_PROBE_FRAMES" in worker
    assert "render=FORMAL_RENDER" in worker
    assert "_complete_formal_worker_audit" not in worker
    assert "copyfile" not in worker
    assert "INTERSECT" not in worker
    assert "CAVITY_LINER" not in worker


def test_step7_probe_command_is_isolated_and_cannot_save_or_overwrite_formal_r1(tmp_path):
    output = (tmp_path / "condenser-hd-probe-r1").resolve()
    command = stage3.step7_probe_blender_command(
        "blender.exe", "candidate.blend", output
    )
    assert command[-2:] == ["--stage3-step7-probe-worker", str(output)]
    assert "--save" not in command
    with pytest.raises(ValueError, match="isolated probe"):
        stage3.build_step7_limited_probe(stage3.FORMAL_OUTPUT_ROOT)


def _synthetic_step7_probe_renderer(staging, authority, blender=None):
    frames_root = staging / "frames"
    frames_root.mkdir(parents=True)
    records = []
    for position, frame_index in enumerate(stage3.STEP7_PROBE_FRAMES):
        path = frames_root / f"frame-{frame_index:03d}.png"
        Image.new(
            "RGBA",
            (1280, 900),
            (70 + position * 8, 90 + position * 7, 110 + position * 6, 255),
        ).save(path)
        records.append(
            {
                "index": frame_index,
                "progress": stage3.approved_motion_progress()[frame_index],
                "path": f"frames/{path.name}",
                "sha256": stage3.sha256(path),
            }
        )
    audit = {
        "schema": stage3.STEP7_PROBE_WORKER_SCHEMA,
        "unit": CONDENSER,
        "render": stage3.FORMAL_RENDER,
        "frameIndices": list(stage3.STEP7_PROBE_FRAMES),
        "candidateBlendSha256Before": stage3.EXPECTED_CANDIDATE_BLEND_SHA256,
        "candidateBlendSha256After": stage3.EXPECTED_CANDIDATE_BLEND_SHA256,
        "candidateBlendSaved": False,
        "temporaryDataBlocksRemaining": [],
        "frames": records,
    }
    (staging / "render-audit.json").write_text(
        json.dumps(audit, indent=2), encoding="utf-8"
    )
    return audit


def test_step7_probe_builds_equal_size_visual_review_and_complete_light_timeline(tmp_path, stage3_evidence):
    output = tmp_path / "condenser-hd-probe-r1"
    report = stage3.build_step7_limited_probe(
        output, renderer=_synthetic_step7_probe_renderer
    )

    assert report["frameIndices"] == [0, 20, 21, 22, 24]
    assert len(list((output / "frames").glob("*.png"))) == 5
    assert len(list((output / "baseline-lowres").glob("*.png"))) == 5
    assert report["endpointsRenderedWithApprovedLinefix"] is True
    assert report["endpointSource"] == "isolated-step7-probe-render"
    assert report["formalR1UnchangedSha256"] == stage3.sha256(
        stage3.FORMAL_OUTPUT_ROOT
        / "twinkle-stage3-dual-hotspot-motion-manifest.json"
    )
    assert report["inspectionLight"] == {
        "source": "stage1-approved-assets",
        "fadeInMs": 900,
        "holdMs": 500,
        "fadeOutMs": 700,
        "chamberMechanicalFramesRerendered": False,
    }
    html = (output / "review" / "index.html").read_text(encoding="utf-8")
    assert "步骤七正式审核" in html
    assert "步骤七可以通过" in html
    assert "阶段三收口" in html
    assert "humanVisualApproved=false" in html
    assert "black-line-dynamic-review.gif" in html
    assert 'id="expand"' in html
    assert 'id="close"' in html
    assert 'id="pause"' in html
    assert 'id="reduced"' in html
    assert "等显示尺寸" in html
    assert "900" in html and "500" in html and "700" in html
    assert "inspection-unlit.png" in html
    assert "inspection-lit.png" in html
    assert "lightFadeInObserved" in html
    assert "lightHoldObserved" in html
    assert "lightFadeOutObserved" in html
    assert "fetch('/result'" in html
    assert (output / "review" / "equal-size-contact-sheet.png").is_file()
    with Image.open(output / "review" / "black-line-dynamic-review.gif") as gif:
        assert gif.size == (1280, 490)
        assert gif.n_frames == 5
        assert gif.info["duration"] == 700
    assert report["machinePassed"] is False
    assert report["humanVisualApproved"] is False
    assert report["authorizesFull25"] is False


def test_step7_probe_diagnosis_exposes_current_r1_endpoint_and_light_review_failures(stage3_evidence):
    diagnosis = stage3.diagnose_formal_step7_failures(stage3.FORMAL_OUTPUT_ROOT)
    assert diagnosis["currentStep7Passes"] is False
    assert diagnosis["inspectionLightReviewPresent"] is False
    assert diagnosis["legacyEndpointFrames"] == [0, 24]
    assert diagnosis["movingRoiScan"]["heightPeakFrame"] == 21
    assert diagnosis["movingRoiScan"]["contrastPeakFrame"] == 22
    assert diagnosis["recommendedProbeFrames"] == [0, 20, 21, 22, 24]


def test_step7_browser_evidence_promotes_only_the_machine_gate(tmp_path, stage3_evidence):
    output = tmp_path / "condenser-hd-probe-r1"
    stage3.build_step7_limited_probe(
        output, renderer=_synthetic_step7_probe_renderer
    )
    result_root = output / "browser-results"
    result_root.mkdir()
    (result_root / "chrome-151.json").write_text(
        json.dumps(
            {
                "browserId": "chrome-151",
                "passed": True,
                "imagesLoaded": True,
                "equalDisplaySize": True,
                "lightFadeInObserved": True,
                "lightHoldObserved": True,
                "lightFadeOutObserved": True,
                "isolatedUserDataRemoved": True,
            }
        ),
        encoding="utf-8",
    )

    report = stage3.finalize_step7_browser_evidence(output, "chrome-151")

    assert report["machinePassed"] is True
    assert report["humanVisualApproved"] is False
    assert report["authorizesFull25"] is False
    assert report["authorizesFormalReplacement"] is False
    assert report["authorizesStage4"] is False
