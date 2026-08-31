import json
import math
from pathlib import Path
from types import SimpleNamespace

from PIL import Image, ImageDraw


def _write_png(path: Path, color, *, size=(640, 450)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", size, color)
    draw = ImageDraw.Draw(image)
    draw.rectangle(
        (size[0] // 4, size[1] // 4, size[0] * 3 // 4, size[1] * 3 // 4),
        outline=(245, 247, 249),
        width=max(1, size[0] // 80),
    )
    image.save(path, format="PNG", compress_level=9)


def _make_authorities(stage4, root: Path):
    source = root / "source.blend"
    candidate = root / "candidate.blend"
    source.write_bytes(b"synthetic stage4 source blend\n")
    candidate.write_bytes(b"synthetic stage4 candidate blend\n")

    stage1_root = root / "stage1"
    units = {}
    cameras = {
        stage4.CHAMBER: {
            "location": [1.2, -0.3, 0.9],
            "target": [0.25, 0.15, 0.2],
        },
        stage4.CONDENSER: {
            "location": [0.8, 0.5, 0.7],
            "target": [0.15, 0.1, 0.1],
        },
    }
    for index, unit in enumerate(stage4.SEMANTIC_UNITS):
        relative = f"assets/{unit}-focused.png"
        asset = stage1_root / relative
        _write_png(asset, (70 + index * 45, 105 + index * 20, 145))
        units[unit] = {
            "cameraPresetId": f"fixture-{index}",
            "camera": {
                **cameras[unit],
                "lensMm": 58.0,
                "sensorWidthMm": 36.0,
                "shiftX": 0.0,
                "shiftY": 0.0,
            },
            "rootObjects": [f"FIXTURE_ROOT_{index}"],
            "fullOffsetsM": {"assembly": [0.03, 0.01, -0.02]},
            "frames": {
                "focused-settled": {
                    "asset": relative,
                    "sha256": stage4.sha256(asset),
                }
            },
        }
    stage1 = {
        "schema": "twinkle-route1-camera-board-v4",
        "source": {"path": str(source), "sha256": stage4.sha256(source)},
        "candidateBlend": {
            "path": str(candidate),
            "sha256": stage4.sha256(candidate),
        },
        "renderProfile": {
            "engine": "BLENDER_EEVEE",
            "resolution": [1280, 900],
            "samples": 512,
            "imageFormat": "PNG",
            "filmTransparent": False,
            "viewTransform": "AgX",
            "look": "AgX - Medium High Contrast",
            "exposure": -1.6,
            "gamma": 1.0,
        },
        "units": units,
    }
    stage1_manifest = stage1_root / "camera-board-manifest.json"
    stage1_manifest.parent.mkdir(parents=True, exist_ok=True)
    stage1_manifest.write_text(
        json.dumps(stage1, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    stage3_root = root / "stage3-r2"
    inventory = {}
    for unit, directory in (
        (stage4.CHAMBER, "chamber-frames"),
        (stage4.CONDENSER, "frames"),
    ):
        for frame in range(25):
            relative = f"{directory}/frame-{frame:03d}.png"
            path = stage3_root / relative
            base = 60 if unit == stage4.CHAMBER else 120
            _write_png(path, (base + frame * 3, 95 + frame * 2, 135 + frame))
            inventory[relative] = stage4.sha256(path)
    for name, color in (
        ("inspection-unlit.png", (85, 105, 125)),
        ("inspection-lit.png", (170, 185, 200)),
    ):
        relative = f"review/{name}"
        path = stage3_root / relative
        _write_png(path, color)
        inventory[relative] = stage4.sha256(path)
    stage3 = {
        "schema": "twinkle-stage3-step7-full-review-v1",
        "machinePassed": True,
        "humanVisualApproved": True,
        "stage3Closed": True,
        "authorizesStage4": False,
        "frameCountPerUnit": 25,
        "inventorySha256": inventory,
    }
    stage3_manifest = stage3_root / "step7-full-review-manifest.json"
    stage3_manifest.write_text(
        json.dumps(stage3, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return SimpleNamespace(
        source=source,
        candidate=candidate,
        stage1_manifest=stage1_manifest,
        stage3_manifest=stage3_manifest,
    )


def _qualification(stage4, unit, entries):
    interval = (
        [{"start": 62, "end": 11, "wraps": True}]
        if unit == stage4.CHAMBER
        else [{"start": 87, "end": 8, "wraps": True}]
    )
    qualified_frames = [index for index in range(96) if index != 50]
    physical = [
        {
            "physicalFrameIndex": index,
            "status": "visible",
            "projection": [0.45, 0.5],
            "machineQualified": index in qualified_frames,
        }
        for index in range(96)
    ]
    candidates = []
    for entry in entries:
        candidates.append(
            {
                "frameIndex": entry,
                "angleDegrees": entry * 3.75,
                "sourcePng": f"frames/frame-{entry:03d}.png",
                "hotspotStatus": "visible",
                "visualCueZh": "机器合格总览出口",
                "componentRecognizability": {
                    "semanticId": unit,
                    "authorityState": "complete-overview-assembly",
                    "usesFocusOrExtractState": False,
                    "projectionMethod": "twinkle_camera_projection-authority-hull",
                    "visibleFraction": 1.0,
                    "visibleArea": 0.2,
                    "hotspotStatus": "visible",
                    "thresholds": dict(
                        stage4.C360_F96_COMPONENT_RECOGNIZABILITY[unit]
                    ),
                    "criteria": {
                        "minimumVisibleWidth": True,
                        "minimumVisibleHeight": True,
                        "minimumVisibleArea": True,
                        "minimumVisibleFraction": True,
                        "minimumHotspotSurfaceFacingDot": True,
                    },
                    "gatePassed": True,
                    "humanReviewStatus": "approved",
                },
            }
        )
    return {
        "physicalFrames": physical,
        "logicalFrames": [dict(record) for record in physical],
        "machineQualifiedPhysicalFrames": qualified_frames,
        "machineQualifiedCyclicIntervals": interval,
        "componentRecognizabilityQualifiedFrames": list(range(96)),
        "initialEntryFrameSet": list(entries),
        "entryCandidates": candidates,
        "entrySelection": {
            "recognizabilityGateApplied": True,
            "maximumCyclicDistanceFrames": 39,
        },
        "turnPlanWorstCase": {
            "turnDurationMs": 1_975,
            "peakAngularSpeedDegreesPerSecond": 90.0,
            "arrivesStopped": True,
            "enterFocusAfterSettled": True,
        },
        "entryRole": "overview-exit-only",
        "focusRouteGenerated": False,
        "humanEntryApproved": True,
        "humanApproved": True,
        "componentRecognizabilityGateOrder": [
            "machine-visible",
            "complete-overview-component-projection",
            "cyclic-shortest-turn",
        ],
    }


def _make_c360(stage4, root: Path):
    output = root / "orbit-c360-f96-r1"
    frames = []
    for index in range(96):
        relative = f"frames/frame-{index:03d}.png"
        path = output / relative
        _write_png(
            path,
            (55 + index % 80, 85 + (index * 2) % 90, 120 + (index * 3) % 90),
            size=(64, 45),
        )
        angle = math.radians(index * 3.75)
        frames.append(
            {
                "physicalFrameIndex": index,
                "azimuthDegrees": index * 3.75,
                "path": relative,
                "sha256": stage4.sha256(path),
                "camera": {
                    "location": [
                        round(math.cos(angle) * 2.0, 8),
                        round(math.sin(angle) * 2.0, 8),
                        0.8,
                    ],
                    "target": [0.2, 0.1, 0.2],
                    "lensMm": 58.0,
                    "sensorWidthMm": 36.0,
                    "shiftX": 0.0,
                    "shiftY": 0.0,
                },
                "speedMetersPerSecond": 1.0,
                "quality": stage4._frame_quality(path),
                "targetClipped": False,
                "subjectOutOfFrame": False,
                "qualificationByUnit": {
                    unit: {"status": "visible", "projection": [0.45, 0.5]}
                    for unit in stage4.SEMANTIC_UNITS
                },
            }
        )
    qualification = {
        stage4.CHAMBER: _qualification(stage4, stage4.CHAMBER, [6, 65]),
        stage4.CONDENSER: _qualification(stage4, stage4.CONDENSER, [87, 8]),
    }
    (output / "worker-audit.json").write_text(
        json.dumps(
            {
                "schema": "twinkle-stage4-c360-f96-worker-v1",
                "renderedFrameCount": 96,
                "frames": frames,
                "restoration": {
                    "candidateBlendSaved": False,
                    "candidateBlendSha256Before": stage4.EXPECTED_CANDIDATE_BLEND_SHA256,
                    "candidateBlendSha256After": stage4.EXPECTED_CANDIDATE_BLEND_SHA256,
                    "sceneSettingsRestored": True,
                    "temporaryDataBlocksRemaining": [],
                },
            }
        ),
        encoding="utf-8",
    )
    (output / "logical-index-map.json").write_text("[]", encoding="utf-8")
    (output / "camera-path.json").write_text("[]", encoding="utf-8")
    (output / "frame-qualification.json").write_text(
        json.dumps(qualification), encoding="utf-8"
    )
    _write_png(output / "path-speed.png", (80, 100, 130), size=(320, 180))
    _write_png(
        output / "c360-f96-12-frame-contact-sheet.png",
        (90, 110, 140),
        size=(320, 180),
    )
    review = output / "review" / "index.html"
    review.parent.mkdir(parents=True)
    review.write_text("<html><body>synthetic C360 review</body></html>", encoding="utf-8")
    (output / "review" / "review-data.json").write_text("{}", encoding="utf-8")
    manifest_path = output / "orbit-c360-f96-manifest.json"
    inventory = {
        path.relative_to(output).as_posix(): stage4.sha256(path)
        for path in sorted(output.rglob("*"))
        if path.is_file() and path != manifest_path
    }
    report = {
        "schema": "twinkle-stage4-orbit-c360-f96-v1",
        "authority": {
            "stage1ManifestSha256": stage4.EXPECTED_STAGE1_SHA256,
            "stage3R2ManifestSha256": stage4.EXPECTED_STAGE3_R2_SHA256,
            "candidateBlendSha256": stage4.EXPECTED_CANDIDATE_BLEND_SHA256,
            "surfaceAnchorManifestSha256": stage4.EXPECTED_APPROVED_SURFACE_ANCHOR_MANIFEST_SHA256,
        },
        "orbitProfile": stage4.C360_F96_PROFILE,
        "render": stage4.C360_F96_RENDER,
        "orientationConstraint": "TRACK_TO",
        "anglesDegrees": stage4.c360_f96_angles(),
        "physicalFrameCount": 96,
        "logicalIndexCount": 96,
        "logicalPhysicalFrames": list(range(96)),
        "selectedSurfaceAnchorByUnit": {
            stage4.CHAMBER: "chamber-surface-02",
            stage4.CONDENSER: "condenser-surface-01",
        },
        "frames": frames,
        "qualificationByUnit": qualification,
        "closureMetrics": {
            "duplicateEndpointRendered": False,
            "seamPositionStepRatio": 1.0,
            "seamOrientationStepRatio": 1.0,
            "pixelSeamRatio": 1.0,
        },
        "orientationMetrics": {"flipCount": 0},
        "restoration": {
            "candidateBlendSha256Before": stage4.EXPECTED_CANDIDATE_BLEND_SHA256,
            "candidateBlendSha256After": stage4.EXPECTED_CANDIDATE_BLEND_SHA256,
            "candidateBlendSaved": False,
            "sceneSettingsRestored": True,
            "temporaryDataBlocksRemaining": [],
        },
        "staticContactSheet": {
            "asset": "c360-f96-12-frame-contact-sheet.png",
            "sampledFrameIndices": list(range(0, 96, 8)),
        },
        "reviewPlayer": dict(stage4.C360_F96_REVIEW_PLAYER),
        "renderedFrameCount": 96,
        "totalStage4RenderedToDate": 160,
        "budgetEvidence": {"renderedThisRun": 96, "totalRenderedToDate": 160},
        "machinePassed": True,
        "humanVisualApproved": True,
        "humanEntryApproved": True,
        "c360ReviewApproval": {
            "approvedBy": "user",
            "approvedOn": "2026-08-30",
            "scope": "stage4-c360-f96-visual-hotspots-visible-intervals-and-overview-exit-entry-candidates-only",
            "approvedReviewAsset": "review/index.html",
            "approvedReviewAssetSha256": inventory["review/index.html"],
            "approvedVisibleIntervalsByUnit": {
                unit: qualification[unit]["machineQualifiedCyclicIntervals"]
                for unit in stage4.SEMANTIC_UNITS
            },
            "approvedEntryFrameSetByUnit": {
                unit: qualification[unit]["initialEntryFrameSet"]
                for unit in stage4.SEMANTIC_UNITS
            },
            "authorizesOrbitRepair": False,
            "authorizesStep6": False,
            "authorizesStage5": False,
        },
        "authorizesOrbitRepair": False,
        "authorizesStep6": False,
        "authorizesStage5": False,
        "inventorySha256": inventory,
    }
    manifest_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    stage4.validate_c360_f96(output)
    return output


def _c1_runner(stage4):
    def runner(command, *, cwd):
        staging = Path(command[-1])
        orbit = stage4.validate_c360_f96(stage4.APPROVED_C360_F96)
        authority = stage4.validate_authority()["stage1"]
        contracts = stage4.c1_route_contracts(orbit, authority)
        routes = []
        for index, contract in enumerate(contracts):
            path = staging / "frames" / contract["routeId"] / "keyframe-012.png"
            _write_png(path, (95 + index * 8, 125, 155))
            routes.append(
                {
                    "routeId": contract["routeId"],
                    "path": path.relative_to(staging).as_posix(),
                    "positionErrorM": 0.0,
                    "targetErrorDegrees": 0.0,
                }
            )
        (staging / "worker-audit.json").write_text(
            json.dumps(
                {
                    "schema": "twinkle-stage4-c1-keyframe-worker-v1",
                    "routes": routes,
                    "restoration": {
                        "candidateBlendSaved": False,
                        "candidateBlendSha256Before": stage4.EXPECTED_CANDIDATE_BLEND_SHA256,
                        "candidateBlendSha256After": stage4.EXPECTED_CANDIDATE_BLEND_SHA256,
                        "sceneSettingsRestored": True,
                        "temporaryDataBlocksRemaining": [],
                    },
                }
            ),
            encoding="utf-8",
        )

    return runner


def _c2_runner(stage4):
    def runner(command, *, cwd):
        staging = Path(command[-1])
        contract_file = json.loads(
            (staging / "c2-worker-contracts.json").read_text(encoding="utf-8")
        )
        rendered = [index for index in range(25) if index not in {0, 12, 24}]
        routes = []
        for route_index, contract in enumerate(contract_file["routes"]):
            records = []
            for index in rendered:
                path = staging / "frames" / contract["routeId"] / f"focus-{index:03d}.png"
                _write_png(
                    path,
                    (65 + (route_index * 17 + index) % 120, 100 + index * 3, 145),
                )
                records.append(
                    {
                        "sampleIndex": index,
                        "path": path.relative_to(staging).as_posix(),
                        "expectedPosition": contract["curveSamplePositions"][index],
                        "positionErrorM": 0.0,
                        "targetErrorDegrees": 0.0,
                        "rollDegrees": 0.0,
                        "sha256": stage4.sha256(path),
                    }
                )
            routes.append({"routeId": contract["routeId"], "frames": records})
        (staging / "worker-audit.json").write_text(
            json.dumps(
                {
                    "schema": "twinkle-stage4-c2-full-worker-v1",
                    "contractSha256": contract_file["contractSha256"],
                    "routes": routes,
                    "renderedFrameCount": 176,
                    "restoration": {
                        "candidateBlendSaved": False,
                        "candidateBlendSha256Before": stage4.EXPECTED_CANDIDATE_BLEND_SHA256,
                        "candidateBlendSha256After": stage4.EXPECTED_CANDIDATE_BLEND_SHA256,
                        "sceneSettingsRestored": True,
                        "temporaryDataBlocksRemaining": [],
                    },
                }
            ),
            encoding="utf-8",
        )

    return runner


def make_browser_evidence(stage4, report):
    route_ids = [
        f"{unit}--entry-{entry:03d}--{variant}"
        for unit, entries in (
            (stage4.CHAMBER, (6, 65)),
            (stage4.CONDENSER, (87, 8)),
        )
        for entry in entries
        for variant in ("A", "B")
    ]
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
        "routeCoverage": route_ids,
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
        {
            "scenario": "desktop",
            "browserId": "chromium",
            "viewport": [1440, 1000],
            **success,
        },
        {
            "scenario": "mobile",
            "browserId": "chromium",
            "viewport": [390, 844],
            **success,
        },
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


def build_pending_c2(stage4, output: Path, choices):
    return stage4.build_c2_full_review(
        output,
        choices=choices,
        authorized=True,
        blender=Path("blender.exe"),
        runner=_c2_runner(stage4),
    )


def make_stage4_core_evidence(stage4, root: Path, patcher):
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    authority = _make_authorities(stage4, root)
    patcher.setattr(stage4, "STAGE1_MANIFEST", authority.stage1_manifest)
    patcher.setattr(stage4, "STAGE3_R2_MANIFEST", authority.stage3_manifest)
    patcher.setattr(
        stage4, "EXPECTED_STAGE1_SHA256", stage4.sha256(authority.stage1_manifest)
    )
    patcher.setattr(
        stage4,
        "EXPECTED_STAGE3_R2_SHA256",
        stage4.sha256(authority.stage3_manifest),
    )
    patcher.setattr(
        stage4, "EXPECTED_SOURCE_BLEND_SHA256", stage4.sha256(authority.source)
    )
    patcher.setattr(
        stage4,
        "EXPECTED_CANDIDATE_BLEND_SHA256",
        stage4.sha256(authority.candidate),
    )
    patcher.setattr(
        stage4,
        "EXPECTED_APPROVED_SURFACE_ANCHOR_MANIFEST_SHA256",
        "FIXTURE-SURFACE-ANCHOR-SHA256",
    )

    c360 = _make_c360(stage4, root)
    patcher.setattr(stage4, "APPROVED_C360_F96", c360)

    c1 = root / "c1-keyframe-precheck-r1"
    patcher.setattr(stage4, "C1_KEYFRAME_OUTPUT_ROOT", c1)
    stage4.build_c1_keyframe_precheck(
        c1,
        authorized=True,
        blender=Path("blender.exe"),
        runner=_c1_runner(stage4),
    )

    c2 = root / "c2-full-review-r1"
    choices = {
        stage4.CHAMBER: {6: "A", 65: "B"},
        stage4.CONDENSER: {87: "A", 8: "A"},
    }
    pending = build_pending_c2(stage4, c2, choices)
    stage4.record_c2_browser_evidence(c2, make_browser_evidence(stage4, pending))
    stage4.record_stage4_selection_and_close(
        c2,
        choices=choices,
        approved_on="2026-08-31",
        authorized=True,
    )
    return SimpleNamespace(
        stage1_manifest=authority.stage1_manifest,
        stage3_manifest=authority.stage3_manifest,
        c360=c360,
        c1=c1,
        c2=c2,
        choices=choices,
    )
