import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from PIL import Image, ImageDraw


CHAMBER = "dual_channel_collection_optics_chamber"
CONDENSER = "dual_channel_condenser_lens_assembly"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def write_png(
    path: Path,
    color: tuple[int, int, int],
    *,
    rect=None,
    size: tuple[int, int] = (1280, 900),
) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", size, color)
    if rect is not None:
        ImageDraw.Draw(image).rectangle(rect, fill=(42, 86, 113))
    image.save(path, format="PNG", optimize=False, compress_level=9)
    return sha256(path)


def make_camera_board(root: Path, module) -> SimpleNamespace:
    board = root / "camera-board"
    assets_root = board / "assets"
    candidate = root / "candidate.blend"
    candidate.write_bytes(b"twinkle synthetic camera candidate\n")
    candidate_hash = sha256(candidate)
    frame_hashes = {}

    states = {
        CHAMBER: {
            "focused-settled": 0.0,
            "fasteners-released-seam": 0.06,
            "extract-mid": 0.5,
            "extract-end": 1.0,
        },
        CONDENSER: {"focused-settled": 0.0, "extract-mid": 0.5, "extract-end": 1.0},
    }
    units = {}
    for unit_index, (unit_id, progresses) in enumerate(states.items()):
        frames = {}
        for frame_index, (state, progress) in enumerate(progresses.items()):
            relative = f"assets/{unit_id}--{state}.png"
            frame_hash = write_png(
                board / relative,
                (70 + unit_index * 50 + frame_index * 4, 95 + frame_index * 3, 120 + frame_index * 2),
            )
            frame_hashes[relative] = frame_hash
            frames[state] = {
                "asset": relative,
                "sha256": frame_hash,
                "progress": progress,
                "modelSha256": candidate_hash,
                "renderBatchId": "fixture-batch",
                "renderProfileId": "fixture-profile",
                "lightRigHash": "fixture-light",
                "materialRuleHash": "fixture-material",
                "colorManagementHash": "fixture-color",
            }
            if unit_id == CHAMBER:
                frames[state]["componentOffsetsM"] = {
                    "bottomCover": [0.0, 0.0, round(-0.14 * progress, 8)],
                    "sidePanel": [0.0, round(-0.10 * progress, 8), 0.0],
                }
            else:
                frames[state]["cleanupAudit"] = {
                    "method": "ffmpeg-removelogo-bitmap-mask",
                    "outsideMaskChangedPixels": 0,
                }
        units[unit_id] = {"frames": frames, "semanticId": unit_id}

    inspection_relative = "assets/chamber-inspection-lit.png"
    inspection_hash = write_png(board / inspection_relative, (112, 128, 144))
    units[CHAMBER].update(
        {
            "displayNameZh": "双通道收集光学腔体",
            "rootObjects": ["DetectBox_Bottom_Mala2020:1", "Side2_optics:1"],
            "timingMs": {"settledHold": 200, "seam": 240, "acceleratedTravel": 760},
            "panelCopy": "紧固件解除后，底盖/侧板沿法线移开。",
            "hideRenderUsed": False,
            "mirror3IdentityStatus": "reference-only",
            "inspectionLight": {
                "baseState": "extract-end",
                "asset": inspection_relative,
                "sha256": inspection_hash,
                "transitionMs": {"enter": 900, "hold": 500, "exit": 700},
                "maskAudit": {"outsideMaskChangedPixels": 0},
            },
        }
    )
    units[CONDENSER].update(
        {
            "displayNameZh": "聚光镜组件",
            "legacyAcceptedHashes": {
                "focused-settled": "F60DE02B9A9612036FBDAB7E4EF35792CD2F20F59D47565CAE72D6D444BF837D",
                "extract-mid": "2B886A06E115F410582A7E1CA45F751CEB5D6D4A44E00A758754D5470DA20C34",
                "extract-end": "BD605CD7018B9505B0394623D1858428926CE5580E0F4A3764A28342240D1FBC",
            },
            "inspectionLight": None,
        }
    )
    render_profile = {
        "id": "fixture-profile",
        "frameCount": 7,
        "sharedHiddenObjects": ["WS_Studio_Floor"],
        "lightRigHash": "fixture-light",
        "materialRuleHash": "fixture-material",
        "colorManagementHash": "fixture-color",
    }
    manifest = {
        "schema": "twinkle-route1-camera-board-v4",
        "candidateBlend": {"path": str(candidate), "sha256": candidate_hash},
        "units": units,
        "renderProfile": render_profile,
        "renderProfileId": render_profile["id"],
        "renderBatchId": "fixture-batch",
        "humanReviewRequired": True,
        "humanReviewApproved": True,
        "humanApproval": module.HUMAN_APPROVAL,
        "productionPageChanged": False,
        "candidateBlendSaved": False,
        "designAuthority": {
            CHAMBER: {
                "threadId": "01a02ff9-18a2-7da3-a250-12dc45e86ff9",
                "sourceEvidence": {
                    "irSideContextSha256": "CC7CB230CFD2065A7D312E56D213AD57DB835D677877D39D55F8108ED32E65AF",
                    "simultaneousTerminalSha256": "A681491EEA32638261583E9CEE6102A530EA14D4066F9F905885C548A2B529EB",
                },
            },
            CONDENSER: {
                "kind": "repository-record",
                "legacyAcceptedReference": {
                    "path": str(module.LEGACY_CONDENSER_REFERENCE),
                    "sha256": module.LEGACY_CONDENSER_REFERENCE_SHA256,
                },
            },
        },
        "sceneMutationAudit": {
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
        },
        "reviewSheet": "camera-board-contact-sheet.png",
        "condenserComparisonSheet": "condenser-comparison.png",
        "inspectionReviewSheet": "inspection-comparison.png",
        "reviewEvidence": {},
        "stage1CleanupEvidence": {
            "deletedDirectories": sorted(module.STAGE1_DELETED_DIRECTORIES),
            "frozenSentinels": sorted(module.FROZEN_SENTINELS),
            "deletedSummary": {
                "directories": 29,
                "files": 244,
                "bytes": 118412245,
                "dedicatedCodeAndTestFiles": 4,
                "cacheFiles": 5,
            },
        },
        "visualRepairCleanupEvidence": {
            "directories": 3,
            "files": 42,
            "bytes": 24950197,
            "paths": [
                ".twinkle-shared-light-bracket-20260824",
                ".twinkle-route1-camera-board-light-fix-staging-20260824",
                ".twinkle-route1-camera-board-pre-exposure-fix-20260824",
            ],
        },
    }
    board.mkdir(parents=True, exist_ok=True)
    manifest_path = board / "camera-board-manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    module.create_review_sheets(board)
    boundary_output = root / "boundary-output"
    boundary_output.mkdir()
    for name in module.FROZEN_SENTINELS:
        (boundary_output / name).mkdir()
    return SimpleNamespace(
        root=board,
        manifest=manifest_path,
        candidate_sha256=candidate_hash,
        frame_sha256=frame_hashes,
        boundary_output=boundary_output,
    )


def _write_required_files(root: Path, relatives) -> None:
    for relative in relatives:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix.lower() == ".png":
            write_png(path, (120, 135, 150), size=(640, 450))
        else:
            path.write_text(f"fixture: {relative}\n", encoding="utf-8")


def _stage3_runtime(stage3):
    progress = [
        0.0, 0.0, 0.0, 0.0, 0.004, 0.014, 0.032, 0.06, 0.11, 0.18,
        0.27, 0.38, 0.50, 0.61, 0.70, 0.77, 0.82, 0.86, 0.885, 0.90,
        0.934, 0.961, 0.981, 0.995, 1.0,
    ]
    velocity = [
        0.0, 0.0, 0.0, 0.0, 0.006, 0.014, 0.023, 0.038, 0.060, 0.080,
        0.105, 0.120, 0.120, 0.105, 0.085, 0.065, 0.050, 0.038, 0.026,
        0.020, 0.017, 0.013, 0.009, 0.004, 0.0,
    ]
    travel = stage3.condenser_motion_only_probe_contract()["travel"]
    full_offset = stage3.condenser_motion_only_probe_contract()["fullOffsetM"]
    return {
        "travel": travel,
        "progress": progress,
        "velocityPerFrame": velocity,
        "accelerationPerFrame": [
            velocity[index] - velocity[index - 1] if index else 0.0
            for index in range(25)
        ],
        "componentOffsetsM": [
            [value * sample for value in full_offset] for sample in progress
        ],
        "rigidRelativeMatrixHashes": ["FIXTURE-RIGID"] * 25,
        "rigidLocalMatrixHashes": ["FIXTURE-LOCAL"] * 25,
        "rigidMaxRelativeMatrixDrift": [0.0] * 25,
        "closeFrameIndices": list(reversed(range(25))),
        "pauseEvidence": {
            "frameIndex": 7,
            "heldFrameIndex": 7,
            "resumeFrameIndex": 8,
            "directionBefore": "forward",
            "directionAfter": "forward",
        },
    }


def make_stage3_evidence(root: Path, stage3) -> SimpleNamespace:
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    authority_root = root / "authority"
    authority_manifest = authority_root / "camera-board-manifest.json"
    source = root / "source.blend"
    candidate = root / "candidate.blend"
    source.write_bytes(b"stage3 synthetic source\n")
    candidate.write_bytes(b"stage3 synthetic candidate\n")

    authority_units = {}
    endpoint_hashes = {}
    for unit_index, unit_id in enumerate((stage3.CHAMBER, stage3.CONDENSER)):
        frames = {}
        for state_index, state_name in enumerate(("focused-settled", "extract-mid", "extract-end")):
            relative = f"assets/{unit_id}-{state_name}.png"
            path = authority_root / relative
            frame_hash = write_png(path, (70 + unit_index * 60 + state_index * 8, 90, 120))
            frames[state_name] = {"asset": relative, "sha256": frame_hash}
            endpoint_hashes[(unit_id, state_name)] = frame_hash
        authority_units[unit_id] = {
            "cameraPresetId": f"fixture-{unit_index}",
            "camera": {"location": [unit_index, 1, 2], "target": [0, 0, 0]},
            "rootObjects": (
                ["DetectBox_Bottom_Mala2020:1", "Side2_optics:1"]
                if unit_id == stage3.CHAMBER
                else ["SHOWCASE_GROUP__f_dual_acl_housing"]
            ),
            "fullOffsetsM": (
                {"bottomCover": [0, 0, -0.14], "sidePanel": [0, -0.1, 0]}
                if unit_id == stage3.CHAMBER
                else {"condenserAssembly": [0.034, 0.012, -0.016]}
            ),
            "frames": frames,
        }
    inspection_relative = "assets/chamber-inspection-lit.png"
    inspection_hash = write_png(authority_root / inspection_relative, (130, 145, 160))
    authority_units[stage3.CHAMBER]["inspectionLight"] = {
        "asset": inspection_relative,
        "sha256": inspection_hash,
    }
    authority = {
        "source": {"path": str(source), "sha256": sha256(source)},
        "candidateBlend": {"path": str(candidate), "sha256": sha256(candidate)},
        "renderProfile": {
            "lightRigHash": "fixture-light",
            "materialRuleHash": "fixture-material",
            "colorManagementHash": "fixture-color",
        },
        "units": authority_units,
    }
    authority_manifest.parent.mkdir(parents=True, exist_ok=True)
    authority_manifest.write_text(json.dumps(authority, indent=2), encoding="utf-8")

    format_root = root / "format"
    _write_required_files(format_root, stage3.FORMAT_EXPERIMENT_FILES)
    browser_failure = format_root / "browser-results" / "chrome-151.json"
    browser_failure.parent.mkdir(parents=True, exist_ok=True)
    browser_failure.write_text(json.dumps({"browserId": "chrome-151", "passed": False}), encoding="utf-8")
    format_report = {
        "schema": stage3.FORMAT_EXPERIMENT_SCHEMA,
        "candidate": {"parameterSetCount": 1},
        "browserMatrix": {
            "chrome-151": "validation-failed",
            "chrome-for-testing-150": "not-run-after-video-route-failure",
            "edge-151": "not-run-after-video-route-failure",
            "edge-150": "not-tested",
        },
        "machinePassed": False,
        "videoRouteFailed": True,
        "humanDetailApproved": True,
        "selectedFormat": stage3.FALLBACK_FORMAT,
        "humanApproval": {
            "approvedFormat": stage3.FALLBACK_FORMAT,
            "approvedBy": "user",
            "approvedOn": "2026-08-26",
            "scope": "stage3-step3-format-only",
            "authorizesStep4": False,
        },
        "inventorySha256": {},
    }
    (format_root / "format-experiment.json").write_text(json.dumps(format_report, indent=2), encoding="utf-8")

    pause_evidence = [
        {
            "percent": percent,
            "frameIndex": frame,
            "holdUsesSameFrame": True,
            "resumeFrameIndex": frame + 1,
            "direction": "forward",
        }
        for percent, frame in ((25, 6), (50, 12), (75, 18))
    ]
    chamber_root = root / "chamber-lowres"
    chamber_progress = [stage3.chamber_motion_progress(index) for index in range(25)]
    chamber_frames = []
    for index, progress in enumerate(chamber_progress):
        path = chamber_root / "frames" / f"frame-{index:03d}.png"
        chamber_frames.append(
            {
                "index": index,
                "progress": progress,
                "path": path.relative_to(chamber_root).as_posix(),
                "sha256": write_png(path, (60 + index * 2, 90, 120), size=(640, 450)),
                "componentOffsetsM": {
                    "bottomCover": [0.0, 0.0, -0.14 * progress],
                    "sidePanel": [0.0, -0.1 * progress, 0.0],
                },
                "rootWorldMatrices": {
                    "DetectBox_Bottom_Mala2020:1": [[1]],
                    "Side2_optics:1": [[1]],
                },
            }
        )
    _write_required_files(chamber_root, stage3.CHAMBER_LOWRES_REVIEW_FILES)
    (chamber_root / "review" / "index.html").write_text(
        '"../frames/frame-000.png" "../inspection/enter-000.png" "../inspection/stable.png"',
        encoding="utf-8",
    )
    chamber_report = {
        "schema": stage3.CHAMBER_LOWRES_SCHEMA,
        "unit": stage3.CHAMBER,
        "selectedFormat": stage3.FALLBACK_FORMAT,
        "render": stage3.CHAMBER_LOWRES_RENDER,
        "timingMs": stage3.CHAMBER_LOWRES_TIMING,
        "motion": {
            "frameIndices": list(range(25)),
            "closeFrameIndices": list(reversed(range(25))),
            "progress": chamber_progress,
            "seamProgress": 0.06,
            "bothPanelsSynchronous": True,
        },
        "frames": chamber_frames,
        "pauseEvidence": pause_evidence,
        "inspectionLight": {
            "transitionMs": {"enter": 900, "hold": 500, "exit": 700},
            "handoff": "exit-complete-before-close-frame-23",
        },
        "endpointReferences": {
            "closed": {
                "path": authority_units[stage3.CHAMBER]["frames"]["focused-settled"]["asset"],
                "sha256": authority_units[stage3.CHAMBER]["frames"]["focused-settled"]["sha256"],
            },
            "open": {
                "path": authority_units[stage3.CHAMBER]["frames"]["extract-end"]["asset"],
                "sha256": authority_units[stage3.CHAMBER]["frames"]["extract-end"]["sha256"],
            },
            "inspectionLit": {
                "path": authority_units[stage3.CHAMBER]["inspectionLight"]["asset"],
                "sha256": authority_units[stage3.CHAMBER]["inspectionLight"]["sha256"],
            },
        },
        "quality": {
            "blackFrameCount": 0,
            "duplicateAdjacentFrameCount": 0,
            "endpointPixelMaeVsStage1HalfSize": 0.0,
        },
        "machinePassed": True,
        "humanVisualApproved": True,
        "humanApproval": {
            "approvedUnit": stage3.CHAMBER,
            "approvedBy": "user",
            "approvedOn": "2026-08-26",
            "scope": "stage3-step4-chamber-lowres-only",
            "authorizesStep5": False,
        },
        "authorizesStep5": False,
    }
    (chamber_root / "chamber-lowres-manifest.json").write_text(json.dumps(chamber_report, indent=2), encoding="utf-8")

    condenser_root = root / "condenser-lowres"
    condenser_progress = [stage3.condenser_motion_progress(index) for index in range(25)]
    condenser_frames = []
    for index, progress in enumerate(condenser_progress):
        path = condenser_root / "frames" / f"frame-{index:03d}.png"
        condenser_frames.append(
            {
                "index": index,
                "progress": progress,
                "path": path.relative_to(condenser_root).as_posix(),
                "sha256": write_png(path, (80 + index * 2, 105, 135), size=(640, 450)),
                "componentOffsetsM": {
                    "condenserAssembly": [value * progress for value in (0.034, 0.012, -0.016)]
                },
                "rootWorldMatrices": {"SHOWCASE_GROUP__f_dual_acl_housing": [[1]]},
            }
        )
    _write_required_files(condenser_root, stage3.CONDENSER_LOWRES_REVIEW_FILES)
    condenser_report = {
        "schema": stage3.CONDENSER_LOWRES_SCHEMA,
        "unit": stage3.CONDENSER,
        "selectedFormat": stage3.FALLBACK_FORMAT,
        "render": stage3.CONDENSER_LOWRES_RENDER,
        "motion": {
            "frameIndices": list(range(25)),
            "closeFrameIndices": list(reversed(range(25))),
            "progress": condenser_progress,
        },
        "frames": condenser_frames,
        "pauseEvidence": pause_evidence,
        "inspectionLight": None,
        "cleanup": {
            "method": "ffmpeg-removelogo-bitmap-mask",
            "cleanedFrameCount": 23,
            "outsideMaskChangedPixels": 0,
            "boundsMonotonic": True,
        },
        "endpointReferences": {
            "closed": {
                "path": authority_units[stage3.CONDENSER]["frames"]["focused-settled"]["asset"],
                "sha256": authority_units[stage3.CONDENSER]["frames"]["focused-settled"]["sha256"],
            },
            "open": {
                "path": authority_units[stage3.CONDENSER]["frames"]["extract-end"]["asset"],
                "sha256": authority_units[stage3.CONDENSER]["frames"]["extract-end"]["sha256"],
            },
        },
        "styleReference": {
            "unit": stage3.CHAMBER,
            "manifest": "output/.twinkle-stage3-chamber-lowres-20260826/chamber-lowres-r1/chamber-lowres-manifest.json",
            "humanVisualApproved": True,
        },
        "quality": {
            "blackFrameCount": 0,
            "duplicateAdjacentFrameCount": 0,
            "endpointPixelMaeVsStage1HalfSize": 0.0,
        },
        "machinePassed": True,
        "humanVisualApproved": False,
        "authorizesStep6": False,
    }
    (condenser_root / "condenser-lowres-manifest.json").write_text(json.dumps(condenser_report, indent=2), encoding="utf-8")

    linefix_root = root / "linefix"
    linefix_contract = stage3.condenser_r1_linefix_candidate_contract()
    linefix_frames = []
    for index, progress in enumerate(linefix_contract["motion"]["progress"]):
        path = linefix_root / "frames" / f"frame-{index:03d}.png"
        linefix_frames.append(
            {
                "index": index,
                "progress": progress,
                "path": path.relative_to(linefix_root).as_posix(),
                "sha256": write_png(path, (95 + index * 2, 115, 140), size=(640, 450)),
            }
        )
    _write_required_files(linefix_root, stage3.CONDENSER_LOWRES_REVIEW_FILES)
    linefix_report = {
        **linefix_contract,
        "unit": stage3.CONDENSER,
        "selectedFormat": stage3.FALLBACK_FORMAT,
        "frames": linefix_frames,
        "candidateBlendSaved": False,
        "temporaryDataBlocksRemaining": [],
        "machinePassed": True,
        "humanVisualApproved": True,
        "humanApproval": {
            "approvedUnit": stage3.CONDENSER,
            "approvedBy": "user",
            "approvedOn": "2026-08-27",
            "scope": "stage3-step5-condenser-r1-linefix",
            "authorizesStep6": False,
        },
        "authorizesStep6": False,
    }
    linefix_manifest = linefix_root / "condenser-linefix-manifest.json"
    linefix_manifest.write_text(json.dumps(linefix_report, indent=2), encoding="utf-8")

    motion_root = root / "motion-only"
    runtime = _stage3_runtime(stage3)
    old_frames = []
    new_frames = []
    for index in range(25):
        for label, collection, base in (("old", old_frames, 75), ("new", new_frames, 105)):
            path = motion_root / label / f"frame-{index:03d}.png"
            collection.append(
                {
                    "index": index,
                    "path": path.relative_to(motion_root).as_posix(),
                    "sha256": write_png(path, (base + index * 2, 110, 135), size=(640, 450)),
                }
            )
    _write_required_files(motion_root, stage3.CONDENSER_MOTION_ONLY_REVIEW_FILES)
    (motion_root / "motion-runtime.json").write_text(json.dumps(runtime, indent=2), encoding="utf-8")
    motion_contract = stage3.condenser_motion_only_probe_contract()
    motion_report = {
        **motion_contract,
        "humanVisualApproved": True,
        "humanApproval": {
            "approvedUnit": stage3.CONDENSER,
            "approvedBy": "user",
            "approvedOn": "2026-08-27",
            "scope": "stage3-step5-condenser-motion-only-probe",
            "authorizesR3": False,
            "authorizesStep6": False,
        },
        "machinePassed": True,
        "playbackEvidence": stage3.motion_playback_audit(),
        "visualBaseline": {
            "path": linefix_root.relative_to(root).as_posix(),
            "manifestSha256": sha256(linefix_manifest),
            "humanVisualApproved": True,
        },
        "motionRuntime": runtime,
        "temporaryDataBlocksRemaining": [],
        "blendSha256Before": {"source": sha256(source), "candidate": sha256(candidate)},
        "blendSha256After": {"source": sha256(source), "candidate": sha256(candidate)},
        "oldFrames": old_frames,
        "newFrames": new_frames,
        "quality": {"blackFrameCount": 0, "endpointMaeVsApprovedLinefix": 0.0},
    }
    motion_manifest = motion_root / "motion-only-probe-manifest.json"
    motion_manifest.write_text(json.dumps(motion_report, indent=2), encoding="utf-8")

    patches = {
        "ROOT": root,
        "AUTHORITY_MANIFEST": authority_manifest,
        "EXPECTED_AUTHORITY_SHA256": sha256(authority_manifest),
        "EXPECTED_SOURCE_BLEND_SHA256": sha256(source),
        "EXPECTED_CANDIDATE_BLEND_SHA256": sha256(candidate),
        "FORMAT_OUTPUT_ROOT": format_root,
        "CHAMBER_LOWRES_OUTPUT_ROOT": chamber_root,
        "CONDENSER_LOWRES_OUTPUT_ROOT": condenser_root,
        "CONDENSER_R1_LINEFIX_OUTPUT_ROOT": linefix_root,
        "CONDENSER_MOTION_ONLY_OUTPUT_ROOT": motion_root,
    }
    originals = {name: getattr(stage3, name) for name in patches}
    original_r3_root = stage3.CONDENSER_R3_OUTPUT_ROOT
    original_formal_root = stage3.FORMAL_OUTPUT_ROOT
    original_step7_root = stage3.STEP7_PROBE_OUTPUT_ROOT
    for name, value in patches.items():
        setattr(stage3, name, value)
    try:
        r3_root = root / "r3" / "condenser-lowres-r3"
        patches["CONDENSER_R3_OUTPUT_ROOT"] = r3_root
        stage3.CONDENSER_R3_OUTPUT_ROOT = r3_root
        stage3.build_condenser_r3_candidate(r3_root)

        formal_root = root / "formal" / "twinkle-stage3-dual-hotspot-motion-r1"
        patches["FORMAL_OUTPUT_ROOT"] = formal_root
        stage3.FORMAL_OUTPUT_ROOT = formal_root

        def formal_renderer(staging, authority_record, blender=None):
            audits = {}
            progress = runtime["progress"]
            for unit_id in (stage3.CHAMBER, stage3.CONDENSER):
                frames_root = staging / "units" / unit_id / "frames"
                frames_root.mkdir(parents=True)
                frames = []
                for index in range(25):
                    path = frames_root / f"frame-{index:03d}.png"
                    if unit_id == stage3.CONDENSER and index in (0, 24):
                        state_name = "focused-settled" if index == 0 else "extract-end"
                        source_path = authority_manifest.parent / authority_record["units"][unit_id]["frames"][state_name]["asset"]
                        path.write_bytes(source_path.read_bytes())
                    else:
                        base = 90 if unit_id == stage3.CHAMBER else 150
                        image = Image.new(
                            "RGB",
                            (1280, 900),
                            (base + index * 2, base + 20 + index, base + 40),
                        )
                        if unit_id == stage3.CONDENSER and index in (21, 22):
                            x = round(620 + 316 * progress[index])
                            if index == 21:
                                ImageDraw.Draw(image).line((x, 100, x, 790), fill=(80, 80, 80), width=3)
                            else:
                                ImageDraw.Draw(image).line((x, 300, x, 520), fill=(36, 36, 36), width=3)
                        image.save(path, format="PNG", compress_level=9)
                    frames.append({
                        "index": index,
                        "path": path.relative_to(staging).as_posix(),
                        "sha256": sha256(path),
                    })
                unit = authority_record["units"][unit_id]
                audit = {
                    "schema": "twinkle-stage3-formal-render-audit-v1",
                    "unit": unit_id,
                    "render": stage3.FORMAL_RENDER,
                    "cameraPresetId": unit["cameraPresetId"],
                    "camera": unit["camera"],
                    "rootObjects": unit["rootObjects"],
                    "fullOffsetsM": unit["fullOffsetsM"],
                    "lightRigHash": authority_record["renderProfile"]["lightRigHash"],
                    "materialRuleHash": authority_record["renderProfile"]["materialRuleHash"],
                    "colorManagementHash": authority_record["renderProfile"]["colorManagementHash"],
                    "candidateBlendSha256Before": sha256(candidate),
                    "candidateBlendSha256After": sha256(candidate),
                    "candidateBlendSaved": False,
                    "temporaryDataBlocksRemaining": [],
                    "frames": frames,
                }
                (frames_root.parent / "render-audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
                audits[unit_id] = audit
            return audits

        stage3.build_formal_candidate(formal_root, renderer=formal_renderer)
        formal_results = formal_root / "browser-results"
        formal_results.mkdir()
        for browser_id in ("chrome-151", "chrome-for-testing-150", "edge-151"):
            (formal_results / f"{browser_id}.json").write_text(
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
        stage3.finalize_formal_browser_evidence(formal_root)

        step7_root = root / "step7" / "condenser-hd-probe-r1"
        patches["STEP7_PROBE_OUTPUT_ROOT"] = step7_root
        stage3.STEP7_PROBE_OUTPUT_ROOT = step7_root

        def step7_renderer(staging, authority_record, blender=None):
            frames_root = staging / "frames"
            frames_root.mkdir(parents=True)
            records = []
            for position, index in enumerate(stage3.STEP7_PROBE_FRAMES):
                path = frames_root / f"frame-{index:03d}.png"
                write_png(
                    path,
                    (100 + position * 8, 120 + position * 6, 140 + position * 4),
                )
                records.append(
                    {
                        "index": index,
                        "progress": runtime["progress"][index],
                        "path": f"frames/{path.name}",
                        "sha256": sha256(path),
                    }
                )
            audit = {
                "schema": stage3.STEP7_PROBE_WORKER_SCHEMA,
                "unit": stage3.CONDENSER,
                "render": stage3.FORMAL_RENDER,
                "frameIndices": list(stage3.STEP7_PROBE_FRAMES),
                "candidateBlendSha256Before": sha256(candidate),
                "candidateBlendSha256After": sha256(candidate),
                "candidateBlendSaved": False,
                "temporaryDataBlocksRemaining": [],
                "frames": records,
            }
            (staging / "render-audit.json").write_text(
                json.dumps(audit, indent=2), encoding="utf-8"
            )
            return audit

        stage3.build_step7_limited_probe(step7_root, renderer=step7_renderer)
        step7_results = step7_root / "browser-results"
        step7_results.mkdir()
        (step7_results / "chrome-151.json").write_text(
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
        stage3.finalize_step7_browser_evidence(step7_root, "chrome-151")
    finally:
        for name, value in originals.items():
            setattr(stage3, name, value)
        stage3.CONDENSER_R3_OUTPUT_ROOT = original_r3_root
        stage3.FORMAL_OUTPUT_ROOT = original_formal_root
        stage3.STEP7_PROBE_OUTPUT_ROOT = original_step7_root

    return SimpleNamespace(
        patches=patches,
        format_root=format_root,
        chamber_root=chamber_root,
        condenser_root=condenser_root,
        linefix_root=linefix_root,
        motion_root=motion_root,
        r3_root=r3_root,
        formal_root=formal_root,
        step7_root=step7_root,
        endpoint_sha256={
            "chamber_closed": endpoint_hashes[(stage3.CHAMBER, "focused-settled")],
            "chamber_open": endpoint_hashes[(stage3.CHAMBER, "extract-end")],
            "chamber_inspection": inspection_hash,
            "condenser_closed": endpoint_hashes[(stage3.CONDENSER, "focused-settled")],
            "condenser_open": endpoint_hashes[(stage3.CONDENSER, "extract-end")],
        },
    )
