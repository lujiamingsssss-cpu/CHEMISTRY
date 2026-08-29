import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

from tests.twinkle_stage1_3_fixtures import make_camera_board


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_twinkle_route1_camera_board.py"
BOARD_ROOT = ROOT / "output" / "twinkle-route1-camera-board-r1-1"
MANIFEST_PATH = BOARD_ROOT / "camera-board-manifest.json"
PYTHON = Path(sys.executable)
LEGACY_REFERENCE = ROOT / "scripts" / "assets" / "twinkle_condenser_legacy_reference.png"
LEGACY_REFERENCE_SHA256 = "12364CBBE6AA9F9AC0A382530506A5B16236AFDF55910D3EEB05A01481A8DC0A"

CHAMBER = "dual_channel_collection_optics_chamber"
CONDENSER = "dual_channel_condenser_lens_assembly"
EXPECTED_CANDIDATE_SHA256 = (
    "584EBB7F8F5F5CAEB7AF469DBF02A465DE7016D67A9D64539A018E9F6DDD4FD6"
)
EXPECTED_OLD_CONDENSER_HASHES = {
    "focused-settled": "F60DE02B9A9612036FBDAB7E4EF35792CD2F20F59D47565CAE72D6D444BF837D",
    "extract-mid": "2B886A06E115F410582A7E1CA45F751CEB5D6D4A44E00A758754D5470DA20C34",
    "extract-end": "BD605CD7018B9505B0394623D1858428926CE5580E0F4A3764A28342240D1FBC",
}
EXPECTED_STAGE1_FRAME_SHA256 = {
    "assets/dual-channel-collection-optics-chamber--focused-settled.png": "642FA008CE1F3DFB3C78479E1C49A1A31FAFFBC5174D4D01C0DA822E6CD12829",
    "assets/dual-channel-collection-optics-chamber--fasteners-released-seam.png": "FA9633B205829F591E5CA2410B89CD234FCAAD7C4F4139057CCFB1C7726263E4",
    "assets/dual-channel-collection-optics-chamber--extract-mid.png": "688BBB31C87EC517745AD3941F139EB5DCF129FB09A7D7542361CEF30BA1EE54",
    "assets/dual-channel-collection-optics-chamber--extract-end.png": "9166E1E5EB4F2ABC2B4BD47D5ECE5306DDE118AC2D75EE957CD89F0CB2C5BE08",
    "assets/dual-channel-condenser-lens-assembly--focused-settled.png": "D7CB8F3EF32507317DFE4050CEB935EA7845794A429E0100E29B86DD7506837C",
    "assets/dual-channel-condenser-lens-assembly--extract-mid.png": "FDE78AC2B3918F0FDC8E9E1ECCACA210EA6F9ED00053457A9202A6AF6D070889",
    "assets/dual-channel-condenser-lens-assembly--extract-end.png": "C1281E8B85FE1FE2904FFD0DC7736CBB174A5BA496C6148AE2FE6588451BB319",
}
EXPECTED_STATES = {
    CHAMBER: {
        "focused-settled": 0.0,
        "fasteners-released-seam": 0.06,
        "extract-mid": 0.5,
        "extract-end": 1.0,
    },
    CONDENSER: {
        "focused-settled": 0.0,
        "extract-mid": 0.5,
        "extract-end": 1.0,
    },
}
STAGE1_DELETED_DIRECTORIES = {
    ".twinkle-route1-camera-board-r1-1-pre-connection-oblique-20260823",
    ".twinkle-route1-settled-preview-visible-20260823",
    ".twinkle-route1-settled-preview-f-shifty-neg008-20260823",
    ".twinkle-route1-settled-preview-f-flat-top-20260823",
    ".twinkle-route1-settled-preview-f-topcap-flat-20260823",
    ".twinkle-route1-settled-preview-f-no-weighted-topcap-20260823",
    ".twinkle-route1-settled-preview-f-no-normal-map-20260823",
    ".twinkle-route1-settled-preview-j-soft-layout-20260823",
    ".twinkle-route1-settled-preview-f-soft-layout-20260823",
    ".twinkle-route1-triptych-preview-j-fast-reveal-20260823",
    ".twinkle-route1-triptych-preview-f-fast-reveal-20260823",
    ".twinkle-route1-triptych-preview-j-front-hero-20260824",
    ".twinkle-route1-triptych-preview-f-front-hero-20260824",
    ".twinkle-route1-triptych-preview-j-green-contrast-20260824",
    ".twinkle-route1-triptych-preview-j-pmt-connection-hero-20260824",
    ".twinkle-hotspot-candidate-comparison-20260824",
    ".twinkle-digger-local-window-triptych-20260824",
    ".twinkle-endoscope-camera-probe-20260824",
    ".twinkle-internal-visibility-survey-20260824",
    ".twinkle-collection-box-bottom-tour-20260824",
    ".twinkle-collection-box-bottom-tour-floor-hidden-20260824",
    ".twinkle-collection-box-official-open-tour-20260824",
    ".twinkle-ir-separation-side-context-20260824",
    ".twinkle-bottom-side-sequential-tour-20260824",
    ".twinkle-bottom-side-simultaneous-stable-light-20260824",
}
FROZEN_SENTINELS = {
    "web-blender-page-coordinated-experiment-v7",
    "twinkle-route1-motion-sample-r1-sync",
    ".twinkle-route1-j-optic-detail-sample-r1-1a-failed-contract-rounding-first",
}


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def load_generator_module():
    spec = importlib.util.spec_from_file_location("twinkle_camera_board", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def camera_board(tmp_path):
    module = load_generator_module()
    return make_camera_board(tmp_path, module)


def test_generator_uses_semantic_units_and_authored_cameras_without_candidate_solver():
    module = load_generator_module()
    source = SCRIPT.read_text(encoding="utf-8")

    assert set(module.UNITS) == {CHAMBER, CONDENSER}
    assert "calculate_twinkle_camera_candidates" not in source
    assert "calculate_candidates" not in source
    assert "LEGACY_CONDENSER_MANIFEST" not in source
    assert module.UNITS[CHAMBER]["rootObjects"] == (
        "DetectBox_Bottom_Mala2020:1",
        "Side2_optics:1",
    )
    assert module.UNITS[CHAMBER]["fullOffsets"] == (
        (0.0, 0.0, -0.14),
        (0.0, -0.10, 0.0),
    )
    assert module.AUTHORED_PRESETS[CHAMBER] == {
        "id": "collection-optics-chamber-side-underside",
        "location": (0.411294, 0.420016, 0.371682),
        "target": (0.285227, 0.622304, 0.585193),
        "lensMm": 55.0,
        "sensorWidthMm": 36.0,
        "shiftX": 0.0,
        "shiftY": 0.0,
    }
    assert module.STATE_PROGRESS == EXPECTED_STATES


def test_render_profile_is_one_shared_contract_for_all_seven_frames():
    module = load_generator_module()
    profile = module.RENDER_PROFILE

    assert profile["engine"] == "BLENDER_EEVEE"
    assert profile["resolution"] == (1280, 900, 100)
    assert profile["taaRenderSamples"] == 512
    assert profile["viewTransform"] == "AgX"
    assert profile["look"] == "AgX - Medium High Contrast"
    assert profile["exposure"] == -1.6
    assert profile["gamma"] == 1.0
    assert profile["panelCopy"] == (
        "紧固件解除后，底盖/侧板沿法线移开。"
    )
    assert profile["sharedHiddenObjects"] == ("WS_Studio_Floor",)
    assert set(profile["existingLights"]) == {
        "WS_Key_Softbox",
        "WS_Fill_Softbox",
        "WS_Rim_Light",
        "WS_Front_Bounce",
    }
    assert profile["sharedTechnicalLights"] == {
        "key": {"energy": 10.0, "size": 0.10, "location": (0.34, 0.48, 0.48)},
        "fill": {"energy": 3.5, "size": 0.14, "location": (0.24, 0.66, 0.52)},
    }
    assert module.should_apply_shared_top_plate_material_copy(CHAMBER)
    assert module.should_apply_shared_top_plate_material_copy(CONDENSER)


def test_approved_stage1_repair_contract_is_explicit_and_reproducible():
    module = load_generator_module()
    source = SCRIPT.read_text(encoding="utf-8")

    assert module.AUTHORED_PRESETS[CONDENSER] == {
        "id": "condenser-lens-front-hero-right-15mm",
        "location": (0.43536043, 0.3241443, 0.56380999),
        "target": (0.45065495, 0.62336338, 0.57699472),
        "lensMm": 72.0,
        "sensorWidthMm": 36.0,
        "shiftX": 0.0,
        "shiftY": 0.02,
    }
    assert module.CHAMBER_INSPECTION == {
        "state": "extract-end",
        "asset": "assets/dual-channel-collection-optics-chamber--inspection-lit.png",
        "rawAsset": ".chamber-inspection-raw.png",
        "enterMs": 900,
        "holdMs": 500,
        "exitMs": 700,
        "light": {
            "type": "AREA",
            "energy": 10.0,
            "size": 0.11,
            "cameraRelativeOffset": (-0.012, 0.008, 0.250),
            "aimDepth": 0.115,
        },
        "maskLuma": {"fullAtOrBelow": 35.0, "zeroAtOrAbove": 60.0},
    }
    assert module.CONDENSER_CLEANUP["method"] == "ffmpeg-removelogo-bitmap-mask"
    assert module.CONDENSER_CLEANUP["baseState"] == "extract-end"
    assert module.CONDENSER_CLEANUP["polygon"] == (
        (900, 548),
        (936, 540),
        (960, 790),
        (928, 810),
    )
    assert module.CONDENSER_CLEANUP["protectedCircles"] == (
        (891, 330, 52),
        (891, 540, 52),
        (891, 750, 52),
    )
    assert module.CONDENSER_CLEANUP["statePlateBounds"] == {
        "focused-settled": (0, 70, 650, 692),
        "extract-mid": (206, 174, 812, 752),
        "extract-end": (376, 259, 966, 825),
    }
    assert "removelogo=filename=" in source
    assert "outsideMaskChangedPixels" in source


def test_stage1_human_approval_is_narrow_and_explicit():
    module = load_generator_module()
    assert module.HUMAN_APPROVAL == {
        "approved": True,
        "approvedAt": "2026-08-25",
        "sourceThreadId": "01a0386f-a914-7960-a3c7-f49ab62c9063",
        "scope": "stage1-formal-asset-replacement-and-closeout-only",
        "stage2Authorized": False,
        "deploymentAuthorized": False,
        "publicationAuthorized": False,
    }


def test_condenser_cleanup_scales_from_each_approved_plate_bounds():
    module = load_generator_module()
    reference = module.cleanup_geometry_for_plate_bounds([376, 259, 966, 825])
    assert reference["polygon"] == [list(point) for point in module.CONDENSER_CLEANUP["polygon"]]
    assert reference["protectedCircles"] == [
        list(circle) for circle in module.CONDENSER_CLEANUP["protectedCircles"]
    ]
    shifted = module.cleanup_geometry_for_plate_bounds([206, 174, 812, 752])
    assert shifted["plateBoundsPx"] == [206, 174, 812, 752]
    assert shifted["polygon"] != reference["polygon"]


def test_worker_completion_marker_and_removed_material_name_are_safe():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'if "CAMERA_BOARD_WORKER=" not in result.stdout' in source
    assert "temporary_material_name = temporary_material.name" in source
    assert "temporary_material_name not in bpy.data.materials" in source
    assert "temporary_material.name not in bpy.data.materials" not in source


def test_existing_manifest_is_replaced_by_semantic_seven_frame_contract(camera_board):
    module = load_generator_module()
    manifest = json.loads(camera_board.manifest.read_text(encoding="utf-8"))

    assert manifest["schema"] == "twinkle-route1-camera-board-v4"
    assert module.EXPECTED_CANDIDATE_SHA256 == EXPECTED_CANDIDATE_SHA256
    assert manifest["candidateBlend"]["sha256"] == camera_board.candidate_sha256
    assert sha256(Path(manifest["candidateBlend"]["path"])) == camera_board.candidate_sha256
    assert set(manifest["units"]) == {CHAMBER, CONDENSER}
    assert manifest["renderProfile"]["id"] == manifest["renderProfileId"]
    assert manifest["renderProfile"]["frameCount"] == 7
    assert manifest["renderProfile"]["sharedHiddenObjects"] == ["WS_Studio_Floor"]
    assert manifest["renderBatchId"]
    assert manifest["humanReviewRequired"] is True
    assert manifest["humanReviewApproved"] is True
    assert manifest["humanApproval"] == module.HUMAN_APPROVAL
    assert manifest["productionPageChanged"] is False
    assert manifest["candidateBlendSaved"] is False
    assert manifest["designAuthority"][CHAMBER]["threadId"] == (
        "01a02ff9-18a2-7da3-a250-12dc45e86ff9"
    )
    assert manifest["designAuthority"][CHAMBER]["sourceEvidence"] == {
        "irSideContextSha256": "CC7CB230CFD2065A7D312E56D213AD57DB835D677877D39D55F8108ED32E65AF",
        "simultaneousTerminalSha256": "A681491EEA32638261583E9CEE6102A530EA14D4066F9F905885C548A2B529EB",
    }
    assert manifest["designAuthority"][CONDENSER]["kind"] == "repository-record"
    assert LEGACY_REFERENCE.is_file()
    assert sha256(LEGACY_REFERENCE) == LEGACY_REFERENCE_SHA256
    assert manifest["designAuthority"][CONDENSER]["legacyAcceptedReference"] == {
        "path": str(LEGACY_REFERENCE),
        "sha256": LEGACY_REFERENCE_SHA256,
    }

    assets = []
    for unit_id, expected_states in EXPECTED_STATES.items():
        unit = manifest["units"][unit_id]
        assert list(unit["frames"]) == list(expected_states)
        for state, progress in expected_states.items():
            frame = unit["frames"][state]
            assert frame["progress"] == progress
            assert frame["modelSha256"] == camera_board.candidate_sha256
            assert frame["renderBatchId"] == manifest["renderBatchId"]
            assert frame["renderProfileId"] == manifest["renderProfileId"]
            assert frame["lightRigHash"] == manifest["renderProfile"]["lightRigHash"]
            assert frame["materialRuleHash"] == manifest["renderProfile"]["materialRuleHash"]
            assert frame["colorManagementHash"] == manifest["renderProfile"]["colorManagementHash"]
            image_path = camera_board.root / frame["asset"]
            assert image_path.is_file()
            assert sha256(image_path) == frame["sha256"]
            with Image.open(image_path) as image:
                assert image.size == (1280, 900)
            assets.append(frame["asset"])
    assert len(assets) == len(set(assets)) == 7

    chamber = manifest["units"][CHAMBER]
    seam = chamber["frames"]["fasteners-released-seam"]
    assert chamber["rootObjects"] == [
        "DetectBox_Bottom_Mala2020:1",
        "Side2_optics:1",
    ]
    assert seam["componentOffsetsM"] == {
        "bottomCover": [0.0, 0.0, -0.0084],
        "sidePanel": [0.0, -0.006, 0.0],
    }
    assert chamber["timingMs"] == {
        "settledHold": 200,
        "seam": 240,
        "acceleratedTravel": 760,
    }
    assert chamber["panelCopy"] == "紧固件解除后，底盖/侧板沿法线移开。"
    assert chamber["hideRenderUsed"] is False
    assert chamber["mirror3IdentityStatus"] == "reference-only"
    inspection = chamber["inspectionLight"]
    assert inspection["baseState"] == "extract-end"
    assert inspection["transitionMs"] == {"enter": 900, "hold": 500, "exit": 700}
    assert inspection["maskAudit"]["outsideMaskChangedPixels"] == 0
    inspection_path = camera_board.root / inspection["asset"]
    assert sha256(inspection_path) == inspection["sha256"]
    with Image.open(inspection_path) as image:
        assert image.size == (1280, 900)

    condenser = manifest["units"][CONDENSER]
    assert condenser["legacyAcceptedHashes"] == EXPECTED_OLD_CONDENSER_HASHES
    assert condenser["inspectionLight"] is None
    for frame in condenser["frames"].values():
        assert frame["cleanupAudit"]["method"] == "ffmpeg-removelogo-bitmap-mask"
        assert frame["cleanupAudit"]["outsideMaskChangedPixels"] == 0
    assert manifest["sceneMutationAudit"] == {
        "cameraChanged": False,
        "renderSettingsChanged": False,
        "renderVisibilityChanged": [],
        "objectTransformsChanged": [],
        "materialSlotsChanged": [],
        "newObjectsRemaining": [],
        "objectsMissing": [],
        "temporaryDataBlocksRemaining": [],
        "temporaryLightsRemoved": True,
        "sharedMaterialRestored": True,
    }


def test_name_compatibility_refresh_uses_new_visible_name_without_rerendering(
    tmp_path, monkeypatch, camera_board
):
    module = load_generator_module()
    manifest_text = camera_board.manifest.read_text(encoding="utf-8")
    manifest = json.loads(manifest_text)

    assert manifest["units"][CONDENSER]["displayNameZh"] == "聚光镜组件"
    assert manifest["units"][CONDENSER]["semanticId"] == CONDENSER
    assert "双通道聚光镜组" not in manifest_text

    actual_frames = {
        frame["asset"]: sha256(camera_board.root / frame["asset"])
        for unit in manifest["units"].values()
        for frame in unit["frames"].values()
    }
    assert actual_frames == camera_board.frame_sha256

    review_root = tmp_path / "review-copy"
    shutil.copytree(camera_board.root, review_root)
    from PIL import ImageDraw

    visible_copy = []
    original_text = ImageDraw.ImageDraw.text

    def capture_text(draw, xy, text, *args, **kwargs):
        visible_copy.append(text)
        return original_text(draw, xy, text, *args, **kwargs)

    monkeypatch.setattr(ImageDraw.ImageDraw, "text", capture_text)
    module.create_review_sheets(review_root)

    assert "聚光镜组件" in visible_copy
    assert "双通道聚光镜组" not in visible_copy


def test_name_compatibility_refresh_cli_is_metadata_only(tmp_path, camera_board):
    refresh_root = tmp_path / "camera-board-refresh"
    shutil.copytree(camera_board.root, refresh_root)
    before_frames = {
        relative: sha256(refresh_root / relative)
        for relative in camera_board.frame_sha256
    }

    result = subprocess.run(
        [
            str(PYTHON),
            str(SCRIPT),
            "--refresh-review-metadata-only",
            "--output-root",
            str(refresh_root),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "CAMERA_BOARD_METADATA_REFRESH=" in result.stdout
    assert "CAMERA_BOARD_WORKER=" not in result.stdout
    manifest = json.loads((refresh_root / "camera-board-manifest.json").read_text(encoding="utf-8"))
    assert manifest["units"][CONDENSER]["displayNameZh"] == "聚光镜组件"
    assert {
        relative: sha256(refresh_root / relative)
        for relative in camera_board.frame_sha256
    } == before_frames == camera_board.frame_sha256


def test_name_compatibility_refresh_rejects_existing_backup_without_staging(tmp_path, camera_board):
    module = load_generator_module()
    refresh_root = tmp_path / "camera-board-refresh"
    shutil.copytree(camera_board.root, refresh_root)
    backup_root = tmp_path / ".camera-board-refresh-metadata-refresh-backup"
    backup_root.mkdir()
    directories_before = {path.name for path in tmp_path.iterdir() if path.is_dir()}

    with pytest.raises(RuntimeError, match="metadata refresh backup already exists"):
        module.refresh_review_metadata_only(refresh_root)

    directories_after = {path.name for path in tmp_path.iterdir() if path.is_dir()}
    assert directories_after == directories_before
    assert refresh_root.is_dir()


def test_name_compatibility_refresh_main_never_calls_blender(tmp_path, monkeypatch, camera_board):
    module = load_generator_module()
    refresh_root = tmp_path / "camera-board-refresh"
    shutil.copytree(camera_board.root, refresh_root)
    blender_calls = []

    def reject_blender(*args, **kwargs):
        blender_calls.append((args, kwargs))
        raise AssertionError("metadata-only refresh invoked Blender")

    monkeypatch.setattr(module, "run_blender", reject_blender)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(SCRIPT),
            "--refresh-review-metadata-only",
            "--output-root",
            str(refresh_root),
        ],
    )

    module.main()

    assert blender_calls == []


def test_name_compatibility_refresh_rolls_back_publish_failure(tmp_path, monkeypatch, camera_board):
    module = load_generator_module()
    refresh_root = tmp_path / "camera-board-refresh"
    shutil.copytree(camera_board.root, refresh_root)

    def inventory(root):
        return {
            path.relative_to(root).as_posix(): sha256(path)
            for path in root.rglob("*")
            if path.is_file()
        }

    inventory_before = inventory(refresh_root)
    original_replace = module.os.replace
    replace_calls = 0

    def fail_staging_publish_once(source, target):
        nonlocal replace_calls
        replace_calls += 1
        if replace_calls == 2:
            raise OSError("injected staging publish failure")
        return original_replace(source, target)

    monkeypatch.setattr(module.os, "replace", fail_staging_publish_once)

    with pytest.raises(OSError, match="injected staging publish failure"):
        module.refresh_review_metadata_only(refresh_root)

    assert inventory(refresh_root) == inventory_before
    assert not (tmp_path / ".camera-board-refresh-metadata-refresh-backup").exists()
    assert not list(tmp_path.glob(".camera-board-refresh-metadata-refresh-*"))


def test_formal_inventory_contains_only_seven_frames_and_review_evidence(tmp_path, camera_board):
    manifest = json.loads(camera_board.manifest.read_text(encoding="utf-8"))
    assets = {
        frame["asset"]
        for unit in manifest["units"].values()
        for frame in unit["frames"].values()
    }
    expected = {
        *assets,
        manifest["units"][CHAMBER]["inspectionLight"]["asset"],
        "camera-board-manifest.json",
        manifest["reviewSheet"],
        manifest["condenserComparisonSheet"],
        manifest["inspectionReviewSheet"],
    }
    actual = {
        path.relative_to(camera_board.root).as_posix()
        for path in camera_board.root.rglob("*")
        if path.is_file()
    }
    assert actual == expected

    with Image.open(camera_board.root / manifest["reviewSheet"]) as image:
        assert image.size == (960, 592)
    with Image.open(camera_board.root / manifest["condenserComparisonSheet"]) as image:
        assert image.size == (960, 518)
    with Image.open(camera_board.root / manifest["inspectionReviewSheet"]) as image:
        assert image.size == (960, 372)
    assert manifest["reviewEvidence"] == {
        "sevenFrameContactSheet": {
            "asset": manifest["reviewSheet"],
            "sha256": sha256(camera_board.root / manifest["reviewSheet"]),
        },
        "condenserComparisonSheet": {
            "asset": manifest["condenserComparisonSheet"],
            "sha256": sha256(camera_board.root / manifest["condenserComparisonSheet"]),
        },
        "inspectionLightComparisonSheet": {
            "asset": manifest["inspectionReviewSheet"],
            "sha256": sha256(camera_board.root / manifest["inspectionReviewSheet"]),
        },
    }

    existing = tmp_path / "already-exists"
    existing.mkdir()
    marker = existing / "keep.txt"
    marker.write_text("keep", encoding="utf-8")
    result = subprocess.run(
        [str(PYTHON), str(SCRIPT), "--output-root", str(existing)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "output root already exists" in result.stderr
    assert marker.read_text(encoding="utf-8") == "keep"


def test_stage1_cleanup_and_frozen_boundaries_are_reproducible(camera_board):
    manifest = json.loads(camera_board.manifest.read_text(encoding="utf-8"))
    evidence = manifest["stage1CleanupEvidence"]
    assert set(evidence["deletedDirectories"]) == STAGE1_DELETED_DIRECTORIES
    assert set(evidence["frozenSentinels"]) == FROZEN_SENTINELS
    assert evidence["deletedSummary"] == {
        "directories": 29,
        "files": 244,
        "bytes": 118412245,
        "dedicatedCodeAndTestFiles": 4,
        "cacheFiles": 5,
    }
    output = camera_board.boundary_output
    assert all(not (output / name).exists() for name in STAGE1_DELETED_DIRECTORIES)
    assert all((output / name).exists() for name in FROZEN_SENTINELS)
    assert manifest["visualRepairCleanupEvidence"] == {
        "directories": 3,
        "files": 42,
        "bytes": 24950197,
        "paths": [
            ".twinkle-shared-light-bracket-20260824",
            ".twinkle-route1-camera-board-light-fix-staging-20260824",
            ".twinkle-route1-camera-board-pre-exposure-fix-20260824",
        ],
    }
    assert all(
        not (output / name).exists()
        for name in manifest["visualRepairCleanupEvidence"]["paths"]
    )


def test_probe_validates_both_semantic_units_without_writing_assets(tmp_path, monkeypatch):
    module = load_generator_module()
    probe_output = tmp_path / "probe-must-not-exist"
    probe = {
        "schema": "twinkle-route1-authored-camera-presets-v3",
        "rendersWritten": 0,
        "units": {unit_id: {} for unit_id in module.UNITS},
    }

    def fake_probe(output_root, probe_only=False):
        assert Path(output_root) == probe_output
        assert probe_only is True
        print("CAMERA_BOARD_PROBE=" + json.dumps(probe))

    monkeypatch.setattr(module, "run_blender", fake_probe)
    monkeypatch.setattr(
        sys,
        "argv",
        [str(SCRIPT), "--probe-only", "--output-root", str(probe_output)],
    )
    module.main()
    assert not probe_output.exists()
    assert probe["schema"] == "twinkle-route1-authored-camera-presets-v3"
    assert probe["rendersWritten"] == 0
    assert set(probe["units"]) == {CHAMBER, CONDENSER}


def test_fixture_frame_hash_gate_rejects_tampering(camera_board):
    module = load_generator_module()
    relative = next(iter(camera_board.frame_sha256))
    (camera_board.root / relative).write_bytes(b"tampered")
    with pytest.raises(RuntimeError, match="frame hash mismatch"):
        module.validate_output(camera_board.root)
